# L7b · 实例级 XSUM（先算每个实例，再取药物中位数）（设计文档）

- 状态：方案待人工确认（只出文档，未实施）
- 基线：LMNA `main` @ `315f965`
- 依赖：L7a（landmark 签名优先 memmap）；数值口径依赖 L1（KS 符号/XSUM 方向）与 L3（判档/夹具）

## 1. 结论摘要

论文口径是“对每个实验实例算 XSUM，再按药物取中位数”；当前代码是“先按药物对每个基因的 z 取中位数，再算 XSUM”。两者数学上不可交换：

```
median_i( Σ_up z_i − Σ_down z_i )  ≠  Σ_up median_i(z_i) − Σ_down median_i(z_i)
```

- 在 L7a 的签名优先层上，实例级实现只需读 `(205034, 978)` float32 = **802 MB**，计算 `205034 × 978` 次加法，结果向量 0.82 MB，按药物中位数后 79 KB。
- 单次新签名的实例级打分：冷读约 2 s（459 MB/s）+ CPU 0.1–0.3 s + 分组中位数 0.3–1 s，合计 **约 1–3 s**；热页缓存 <1 s。
- 与现有“中位数矩阵”口径对比（同一批 19,811 个药物、同一签名）：
  - 全局排名 Spearman **0.985–0.997**，Top-100 重合 **100/100**，Top-500 重合 **498–499/500**；
  - 但中段排名位移可达 **6,186–6,877 位**；已知药物百分位变化最大约 **+0.30**（例如 dabrafenib 0.285→0.502，bicalutamide 0.429→0.721，atorvastatin 0.487→0.734）。
- 初步“抑制剂找回率”对比（29 对基因-药物，服务器只读、内存内计算）显示：**两种做法都没有把已知抑制剂排进前 100/500（双向统计均为 0/29）**，细胞系匹配后的 11 组最好百分位也只有 0.285（A）/0.292（B）。这说明当前 L5 数据 + 简单 top-25 KS 签名不足以做找回率结论，必须复用 L3 报告 4.4b 的校准夹具（394 个靶点、LOHO≥0.5 的绿档签名）。

推荐：

1. 先实现实例级路径，但用开关 `LMNA_XSUM_MODE=median_first|instance_first` 控制，默认仍 `median_first`；
2. 用 L3 的绿档靶点 + 已知抑制剂夹具复跑，确认 `instance_first` 是否稳定改善 Recall@10% / AUROC；
3. 在切换默认值前，重跑 L4 的药物级 null/FDR 校准（报告 4.4b 本身是实例级口径）；
4. 不在本任务中改变业务代码。

## 2. 现状与证据

### 2.1 代码事实

- `backend/drug_median_cache.py:19-82`：`_ensure_drug_median_cache` 先按 `pert_iname` 分组，对每个基因取所有实例的 `np.median`（第 72 行），得到 `(978, n_drugs)` 矩阵；缓存文件 `_drug_median_matrix.npy` 74 MiB，`_drug_names.csv` 19,811 行（服务器实测）。
- `backend/drug_scorer.py:45-85`：`_xsum_score` 在药物中位数矩阵上计算 `Σ_up z − Σ_down z`（第 56-60 行），再排序。
- `backend/drug_scorer.py:87-135`：`_wtcs_score` 同样在中位数矩阵上算排名权重，即“先中位数后 WTCS”。
- 论文口径（任务原文/报告 4.4b）：先对每个实例算 `Σz(up) − Σz(down)`，再按药物取中位数；报告 4.4b 的阈值也是这个口径。
- 数据规模（服务器只读统计）：`trt_cp` **205,034** 个实例、**19,811** 个唯一 `pert_iname`（`pert_id` 20,413 个）；每药物实例数中位数 5、均值 10.35、最大 1,323。

### 2.2 为什么不是简单换一行

`drug_median_cache.py` 的缓存是“每药物一个 978 维向量”，实例级口径要求保留“每实例一个标量分数”。两种做法的存储对象不同：

- 旧：`(978, 19,811)` = 73.9 MiB，查询时 O(978×19,811) 点积；
- 新：`(205,034,)` = 0.82 MB，查询时需要先对 205,034 个实例算分（读 802 MB），再分组中位数。

因此实例级不是“把 `np.median` 移个位置”，而是换一层缓存/索引结构。

## 3. 目标与非目标

### 3.1 目标

- 提供与论文一致的实例级 XSUM 计算路径，结果可复现、可缓存、可回滚。
- 给出内存/耗时估算，并在真实数据上量化两种口径的排名差异。
- 设计一个可执行的夹具对比方案（Recall@K、AUROC、MRR、Top-K 重合）。

### 3.2 非目标

- 不改变 XSUM 的符号约定；符号由 L1 决定（当前代码的 `up/down` 命名与 KS 符号存在历史歧义）。
- 不实现 WTCS 的实例级版本（可复用同一索引，但优先级低；见 §8）。
- 不重训/重标定 L3 判档阈值；只指出需要重标定。

## 4. 数据格式与索引

### 4.1 药物实例索引 `drug_instances_v1/`

建议构建一次、随数据版本更新：

```
<DATA_DIR>/derived/drug_instances_v1/
├── instance_sig_rows.npy    # uint32, (205034,)，指向 L7a 的行号
├── drug_codes.npy           # int32, (205034,)，0..19810
├── drug_names.csv           # 19811 行：drug_code,pert_iname
├── drug_scope.json          # all / launched（见 L7c）
└── manifest.json            # 源 sig_info 哈希、计数、构建时间
```

- `instance_sig_rows.npy` 与 `drug_codes.npy` 一一对应；按 `drug_code` 稳定排序，便于批量分组。
- 只包含 `pert_type == "trt_cp"` 且 `pert_iname` 非空的实例；是否排除单实例药物由查询参数决定（默认保留）。
- 行号指向 L7a 的 `(n_sigs, 978)` 层，避免重复存表达值。

### 4.2 结果缓存

```
<CACHE_DIR>/xsum_instance/
├── <signature_hash>_instance_scores.npy   # float32, (205034,), 0.82 MB（可选）
└── <signature_hash>_drug_medians.npz      # drug_names + median, 79 KB
```

- `signature_hash` = 规范化后的 up/down 基因集合 + 数据层版本 + 药物范围 + 方法 + 符号约定版本的 SHA256。
- 只缓存最终 `(drug_name, median)` 即可；实例分数可选，用于调试/复算。
- 缓存与 L2 的版本化一起失效；不要只按基因名做 key。

## 5. 算法与接口

### 5.1 核心函数

```python
# backend/instance_xsum.py（示意，不在本任务提交）
def instance_scores(store, up_idx, down_idx, batch=50000):
    """返回 (n_instances,) float32；按 batch 读 L7a，控制峰值内存。"""
    n = store.n_instances
    out = np.empty(n, dtype=np.float32)
    for s in range(0, n, batch):
        e = min(s + batch, n)
        rows = store.rows[s:e]           # (b, 978)
        out[s:e] = rows[:, up_idx].sum(axis=1) - rows[:, down_idx].sum(axis=1)
    return out

def drug_medians(scores, drug_codes, n_drugs):
    """按 drug_code 分组取中位数；返回 (n_drugs,) float32。"""
    out = np.empty(n_drugs, dtype=np.float32)
    for code in range(n_drugs):
        m = drug_codes == code
        out[code] = np.median(scores[m])
    return out
```

实现细节：

- `up_idx/down_idx` 是 landmark 层列号（0..977），由 `get_gene_symbols()` 的 symbol→idx 映射得到。
- 分组中位数建议用 `np.argsort(drug_codes)` + `np.searchsorted` 预计算边界，避免每次 `scores[mask]` 扫描；中位数用 `np.partition` 或 `np.median`。
- 若 `up_idx` 或 `down_idx` 为空：按现有 `drug_scorer.py` 语义分别跳过对应项；两边都为空则返回全 0 并给出警告。
- 浮点累加顺序：实例分数用 float32 累加即可；如需与论文严格对齐，可提供 `dtype=float64` 选项（内存翻倍，205,034×8=1.64 MB，可接受）。
- 反向/正向模式：`mode=lof|gof`（与 L3 一致）只影响排序方向，不改变分数定义；在结果中显式返回 `mode`。

### 5.2 与 `DrugScorer` 的衔接

```python
class DrugScorer:
    def _xsum_score(self, signature, top_k, bottom_k):
        mode = signature.get("mode", "lof")
        if settings.xsum_mode == "instance_first":
            scores = instance_scores(...)
            med = drug_medians(scores, codes, n_drugs)
        else:
            med = self._drug_matrix[up_idx].sum(0) - self._drug_matrix[down_idx].sum(0)
        order = np.argsort(-med) if mode == "lof" else np.argsort(med)
        ...
```

- 返回结构不变：`method/gene_name/n_up_genes/n_down_genes/top_drugs/bottom_drugs/all_scores`。
- `all_scores` 仍包含 19,811 项；建议存为 `.npz` 或压缩 JSON，避免每个任务 JSON 膨胀（与 L7f 衔接）。
- WTCS 的实例级版本需要“每个实例内 978 个基因的排名”，可在同一索引上分批 `argsort`；成本更高（见 §8），第一期不做。

## 6. 夹具与“抑制剂找回率”实验设计

### 6.1 夹具来源

不要使用临时手写的 29 对作为正式夹具。正式夹具应复用 L3 报告 4.4b 的校准集：

- 靶点：394 个有特异抑制剂的靶点；
- 金标准：每个靶点的已知抑制剂（报告 4.4b 使用的集合）；
- 签名质量：只用 LOHO Jaccard ≥ 0.5 的绿档签名（22 个靶点）作为“强阳性”子集，另用全部可算签名做敏感性分析；
- 细胞系：记录每个正例的药物实例细胞系；分别评测“全部细胞系”和“与 shRNA 主细胞系一致”两种口径；
- 版本：夹具文件、数据层 manifest、L1 符号约定版本三者写入结果。

建议夹具文件（L0 仓库内，不入大数据）：

```tsv
gene    drug    cell_line    source    expected_mode
CDK4    palbociclib    A549    L3-calibration    lof
EGFR    gefitinib    A549    L3-calibration    lof
...
```

### 6.2 指标

- **Recall@K**：已知抑制剂是否落在全部药物的前 K（K=1%、5%、10%）；
- **MRR**：已知抑制剂排名的倒数均值；
- **AUROC**：正例=已知抑制剂，负例=其余药物；
- **配对比较**：同一签名下 A/B 两法的 Recall 差值，1,000 次 bootstrap 的 95% CI；
- **排名稳定性**：全库 Spearman、Top-100/500 重合、最大位移；
- **分层**：绿档 vs 黄档、全部细胞系 vs 细胞系匹配。

### 6.3 本次预实验（只读、内存内，2026-10-17）

由于 L0 夹具尚未合并，先做了一次“可行性预实验”，不作为最终结论：

- 数据：GSE92742 L5，978 landmark，205,034 个 `trt_cp` 实例；
- 签名：每个靶基因的 shRNA 样本，按当前 `SignatureEngine` 的 ranks + KS，取 |KS| 最大的 25 个 up + 25 个 down；
- 正例：手工整理的 29 对高置信“靶点-抑制剂”（ABL1/EGFR/BRAF/ALK/MET/KIT/PDGFRA/MTOR/HMGCR/PTGS2/ESR1/AR/AGTR1/SRC/JAK2/MAP2K1/CDK4/PARP1/AKT1/PIK3CA）；
- 方法 A：先按药物取 z 中位数，再 XSUM（当前代码）；
- 方法 B：先按实例算 XSUM，再按药物取中位数（论文口径）。

结果：

| 指标 | 方法 A | 方法 B |
|---|---|---|
| 29 对中排进前 100（双向） | 0/29 | 0/29 |
| 29 对中排进前 500（双向） | 0/29 | 0/29 |
| 平均百分位（0=最好） | 0.461 | 0.508 |
| 29 对排名 Spearman（A vs B） | 0.486 | — |

细胞系匹配的 11 组（例如 ESR1/MCF7、BRAF/A375、EGFR/A549）：

| 基因/药物/细胞系 | A 百分位 | B 百分位 | 全库 Spearman |
|---|---|---|---|
| ESR1/fulvestrant/MCF7 | 0.515 | 0.618 | 0.989 |
| ESR1/tamoxifen/MCF7 | 0.366 | 0.392 | 0.989 |
| BRAF/vemurafenib/A375 | 0.367 | 0.435 | 0.992 |
| BRAF/dabrafenib/A375 | **0.285** | 0.502 | 0.992 |
| EGFR/gefitinib/A549 | 0.424 | 0.575 | 0.994 |
| HMGCR/simvastatin/HEPG2 | 0.472 | 0.500 | 0.993 |
| HMGCR/atorvastatin/HEPG2 | 0.487 | 0.734 | 0.993 |
| AR/bicalutamide/VCAP | 0.429 | 0.721 | 0.995 |
| MTOR/everolimus/MCF7 | 0.452 | 0.431 | 0.985 |
| MTOR/everolimus/A549 | **0.292** | **0.292** | 0.997 |

全库排名重合（EGFR/A549、ESR1/MCF7）：

- Top-100 重合 100/100，Top-500 重合 498–499/500；
- 最大单药排名位移 6,186–6,877 位。

结论：

1. 两种口径在全库层面高度相关，但中段排名和个别已知药物的百分位可以差 0.2–0.3；不能假设“换个顺序排名不变”。
2. 在当前 L5 + 简单 top-25 KS 签名上，两种口径都没有显示出抑制剂找回能力；这与 L3 报告 4.4b 的“全部靶点中位 AUROC 0.55、绿档 82% 进前 10%”并不矛盾——差别在签名稳定性筛选、金标准集合和 null 校准。正式对比必须用 L3 夹具。
3. 在正式夹具结果出来之前，不应把 `instance_first` 设为默认，也不应据此调整 L4 的 FDR 阈值。

## 7. 内存与耗时估算

| 项目 | 数值 |
|---|---|
| 实例表达矩阵（205,034×978 float32） | 802 MB |
| 实例 XSUM 分数 | 0.82 MB |
| 每药物中位数结果 | 79 KB |
| 旧中位数矩阵 | 73.9 MiB |
| 实例索引（uint32+int32） | 1.64 MB |
| 峰值内存（全量读） | 约 2.7 GB（L7a 映射 1.85 GB + 802 MB + 余量） |
| 峰值内存（batch=50,000） | 约 2.0 GB（196 MB 批 + 映射 + 余量） |
| 单次查询冷读 | 约 2 s（802 MB @459 MB/s） |
| 单次查询热读 | <1 s |
| 单次查询 CPU（分数+中位数） | 0.4–1.3 s |
| 1,000 个签名查询 | 约 15–45 min（热页缓存；取决于 CPU） |
| 全量预计算 8,178 个基因的药物分数（可选） | 648 MB/方法；不解决签名计算瓶颈 |

对比：现有中位数缓存首次构建在 keji 上约 4.3 分钟（按 205,034/473,647 × 10 分钟外推），本机更慢时可能是数十分钟到数小时；实例级把“一次性构建”换成“每查询 1–3 s”，并用页缓存摊薄。

## 8. WTCS（可选，第二阶段）

实例级 WTCS 与 XSUM 不同：每个实例需要先对其 978 个基因做列内排名，再按 up/down 计算加权 KS。成本：

- 每实例排序 978 个 float32：205,034 × 978 log 978 ≈ 2×10^9 次比较；
- 若一次查询全量计算，预计 20–60 s（取决于 CPU/并行）；
- 可缓存每个实例的 int16 排名矩阵：205,034×978×2 = 401 MB；之后每次查询只做加权求和，约 1–3 s。

建议：第一期只做 XSUM；WTCS 等 L7b 的 XSUM 夹具结果确认后再评估，避免同时改两个算法。

## 9. 迁移步骤

1. 先完成 L7a，得到 `(n_sigs, 978)` 层与 `sig_id` 行号映射。
2. 构建 `drug_instances_v1` 索引（一次，几分钟），校验实例数/药物数与 `sig_info` 一致。
3. 实现 `instance_xsum.py` + `DrugScorer` 分支，新增单测（见 §10）。
4. 增加环境变量 `LMNA_XSUM_MODE`（默认 `median_first`）和缓存 key 版本。
5. 在夹具上跑 A/B 对比，产出报告；由人工决定是否切默认。
6. 若切换：同步重跑 L4 的药物级 null/FDR 校准；前端/导出标注“实例级 XSUM”口径；保留旧缓存 30 天用于回滚。
7. 回滚：环境变量改回 `median_first`，清实例级缓存（不影响旧中位数矩阵）。

## 10. 验收清单（实施时执行）

- [ ] 合成矩阵单测：构造 3 个药物 × 2 个实例、up/down 各 2 个基因，手工计算 A/B 结果，断言 A≠B 且各自正确。
- [ ] 单实例药物：A 与 B 结果完全相等。
- [ ] 空 up / 空 down / 两者皆空：行为与现有 `drug_scorer.py` 一致。
- [ ] 分组中位数与 `np.median` 逐药物一致（随机 100 个药物）。
- [ ] 全量 205,034 实例索引的 `drug_codes` 与 `drug_names` 一一对应，计数与 `sig_info` 一致。
- [ ] 性能：单次查询 <5 s（冷）、<2 s（热）；峰值内存 <3 GB（batch 模式）。
- [ ] 夹具报告：A/B 的 Recall@1%/5%/10%、MRR、AUROC、配对 bootstrap CI、全库 Spearman、Top-100/500 重合。
- [ ] 结果 JSON 结构与现有 API 兼容；`all_scores` 不导致单任务文件超过约定大小（与 L7f 一起检查）。
- [ ] 缓存 key 包含数据版本/药物范围/符号约定；L2 的失效测试通过。
- [ ] 回滚开关有效，旧口径结果可复现。

## 11. 工作量估算

| 工作 | 人日 |
|---|---|
| 实例索引构建 + 校验 | 0.5 |
| `instance_xsum.py` + `DrugScorer` 分支 + 单测 | 1.0 |
| 缓存/版本/开关 + L2 衔接 | 0.5 |
| 夹具对比脚本与报告（复用 L3 校准集） | 1.0 |
| 文档/评审/回滚演练 | 0.25 |
| **合计** | **3.25 人日** |
| 可选：实例级 WTCS | +2 人日 |

## 12. 待人工确认

1. 是否以 `instance_first` 作为最终默认口径？建议先用夹具证明它相对 `median_first` 有稳定增益，再切换。
2. 切换后是否同步重跑 L4 的 null/FDR 校准（报告 4.4b 是实例级口径，当前生产阈值可能不匹配）。
3. 正式夹具是否直接复用 L3 校准集的 394 个靶点与已知抑制剂？若是，需要该集合的存放位置与授权。
4. 是否需要在结果中同时返回两种口径的排名（对比模式），还是只返回选定口径？
5. 单实例药物是否保留在分母中（会影响中位数与 FDR 分母）。

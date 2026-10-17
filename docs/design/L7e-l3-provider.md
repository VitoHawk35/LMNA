# L7e · L3Provider（Level 3 + 同板空载体对照重算 robust z）（设计文档）

- 状态：方案待人工确认（只出文档，未实施）
- 基线：LMNA `main` @ `315f965`
- 关联：L1（符号约定）、L3（判档/LOHO）、L7a（landmark 层）、L7b（实例级口径）

## 1. 结论摘要

论文使用 Level 3 原始表达值，按同一块 384 孔板的 vehicle/空载体对照重算 robust z：

```
z = (x − median_control) / (1.4826 × MAD_control)
```

当前 LMNA 用的是 Level 5 MODZ（`backend/l5_provider.py:42-47`），`L3Provider` 只是空壳（`backend/l3_provider.py:22-30`）。

关键可行性结论（本次只读核对）：

- GSE92742 的 Level3 矩阵是 **1,319,138 × 12,328**，压缩文件 **52.4 GB**（`...Level3_INF_mlr12k_n1319138x12328.gctx.gz`）；Level4 53.3 GB。服务器目前只有 Level5（23.36 GB），**没有 Level3/Level4**。
- `inst_info`（12 MB）提供 `rna_plate`、`rna_well`、`pert_type`、`cell_id` 等字段，可用于同板分组。
- **同板对照的选择需要修正任务描述**：shRNA 样本的同板对照主要是 `ctl_vector`（空载体），不是 `ctl_vehicle`。
  - `trt_sh*`：448,737 个 L3 实例、1,467 块板；
  - `ctl_vector`：30,400 个实例、1,715 块板；1,467 块 shRNA 板**全部**有同板 `ctl_vector`，每板中位数 25 个（分位：1/4/25/28/105）；
  - `ctl_vehicle` 与 shRNA 同板的只有 2,323 个实例、172 块板；若只按 `ctl_vehicle` 匹配，448,737 个 shRNA 实例中只有 613 个能匹配上（0.14%），方案不可行。
- 因此 L3Provider 的“同板 vehicle”应对 shRNA 解释为“同板空载体（`ctl_vector`）”；`ctl_vehicle` 用于化合物实验。文档和代码注释必须写清楚，避免实施时选错对照。
- 数据量：只需提取 978 landmark × (448,737 shRNA + 30,400 ctl_vector) = **479,137 × 978 × 4 ≈ 1.87 GB** 的派生层；但提取过程要扫描 52.4 GB gctx，预计 1–3 小时（gzip/解析受限，尚未实测），临时磁盘约 70–120 GB。

推荐：

1. **先做一个 2 人日的可行性 spike**：选 1 个细胞系（如 VCAP）、10 个基因，验证 gctx 解析、板号映射、robust z 数值和样本数；不要直接全量实施。
2. 全量实施的优先级低于 L7a/L7b：L3 的收益是“更接近论文的实例数与统计功效”，但 MODZ 已经平滑，KS 的 p 值下限与 Table S1 不可能完全对上；如果目标只是改善产品排序，L7b 的实例级 XSUM + L7a 的 I/O 修复收益更直接。
3. 若实施，L3Provider 只负责“签名”，药物打分仍用 L5 药物矩阵；不要把两套 z-score 混在同一个药物缓存里。

## 2. 现状与证据

### 2.1 代码事实

- `backend/l3_provider.py:22-30`：构造函数直接 `raise NotImplementedError`，只列出待实现步骤。
- `backend/l5_provider.py:42-47`：L5 直接 mmap `fast_matrix.npy`，即 MODZ z-score。
- `backend/config.py:64`：`DATA_PROVIDER = os.getenv("DATA_PROVIDER", "l5")`；`backend/task_queue.py:36-40` 可以构建 L3Provider，但一构造就抛异常。
- `backend/data_provider.py:82-88`：接口要求 `get_vehicle_samples_for_plate(plate_id)`；L5 实现抛 `NotImplementedError`（`l5_provider.py:139-143`）。
- 论文口径（任务原文）：Level 3 + 同板 vehicle/空载体重算 robust z；每个敲低实例一个样本；论文 84 个实例，L5 约三分之一。

### 2.2 数据事实（GEO + 服务器只读）

| 文件 | 大小 | 说明 |
|---|---|---|
| `GSE92742_Broad_LINCS_Level3_INF_mlr12k_n1319138x12328.gctx.gz` | 52,407,725,132 B（52.4 GB） | Level3 INF，1,319,138 × 12,328 |
| `GSE92742_Broad_LINCS_Level4_ZSPCINF_mlr12k_n1319138x12328.gctx.gz` | 53,291,574,222 B（53.3 GB） | Level4，已做板级 z |
| `GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx.gz` | 21.3 GB | 服务器现有 |
| `GSE92742_Broad_LINCS_inst_info.txt.gz` | 12,046,182 B | 实例→板/孔/扰动类型 |
| `GSE92742_Broad_LINCS_sig_info.txt.gz` | 11,124,404 B | L5 签名元数据 |
| 服务器可用磁盘 | 6.1 TB | 足够放临时/派生数据 |

`inst_info` 列：

```
inst_id, rna_plate, rna_well, pert_id, pert_iname, pert_type,
pert_dose, pert_dose_unit, pert_time, pert_time_unit, cell_id
```

统计（`inst_info` 全表 1,319,138 行）：

| 项目 | 数值 |
|---|---|
| 板数（`rna_plate`） | 3,613 |
| 细胞系 | 76 |
| `trt_cp` | 672,128 |
| `trt_sh`（含 `.cgs/.css`） | 448,737 |
| `trt_oe` | 87,765 |
| `ctl_vector` | 30,400 |
| `ctl_vehicle` | 28,463 |
| `ctl_untrt` | 22,072 |
| shRNA 板数 | 1,467 |
| 有 `ctl_vector` 的 shRNA 板 | 1,467（全部） |
| shRNA 板上 `ctl_vector` 总数 | 25,359；另有 23 个在共享板 |
| 每 shRNA 板 `ctl_vector` 数 | min 1 / 25% 4 / median 25 / 75% 28 / max 105 |
| shRNA 板上 `ctl_vehicle` | 2,323 个（172 块板） |
| 只有 `ctl_vehicle` 同板可用的 shRNA 实例 | 613 / 448,737 |

结论：**L3Provider 的对照选择必须是 `ctl_vector`（shRNA）**。如果任务原文坚持“vehicle”，则只能覆盖 613 个实例，方案不成立；需要在实施前由人工确认这一语义修正。

### 2.3 为什么 L3 与 L5 的数值不能一一对上

- L5 的 MODZ 是跨实例/跨板聚合后的 moderated z-score，已经做过平滑；L3 重算的 robust z 是单实例、单板级别。
- 样本数不同：论文 84 个实例 vs L5 约三分之一；L3 的 448,737 个 shRNA 实例是“所有实例”，按基因聚合后仍可能多于 L5。
- KS 的 null 分布与 p 值下限随样本数变化；Bootstrap 次数也不同（L5 默认 1,000，论文 L3 建议 100,000）。
- 因此验收标准应是“流程正确、数值可复现、样本数合理”，而不是“与论文 Table S1 完全一致”。

## 3. 目标与非目标

### 3.1 目标

- 实现一个可用的 `L3Provider`：读取 L3 派生层，按同板 `ctl_vector` 重算 robust z，输出每个敲低实例的 978 维向量。
- 与 `SignatureEngine` 的 ranks + KS 接口对齐；支持 `n_samples`、`n_hairpins`、`cell_lines` 等元数据。
- 保留 L5 为默认；L3 通过 `DATA_PROVIDER=l3` 或独立开关启用。
- 提供数据准备、校验、回滚步骤和明确的磁盘/时间预算。

### 3.2 非目标

- 不替换 L5 的药物中位数矩阵与药物打分；L3 只影响签名。
- 不保证复现论文 Table S1 的具体数值。
- 不在服务器上安装依赖、重启服务或修改生产目录（数据准备需要另行审批）。
- 不在本任务中写代码/下载数据。

## 4. 数据准备设计

### 4.1 下载与校验

1. 从 GEO FTP 下载 Level3 gctx.gz（52.4 GB）到服务器**临时目录**（例如 `/home/keji/l3_tmp/`，不写 `~/cmap`、`~/LMNA`）。
2. 校验 GEO 提供的 SHA512（`GSE92742_SHA512SUMS.txt.gz`）。
3. 同时下载 `inst_info`、`gene_info`、`sig_info`（约 24 MB）。
4. 记录下载时间、文件大小、SHA512 到 `manifest.json`。

### 4.2 解析与提取

目标：只保留 978 landmark 行 + 需要的列（shRNA + `ctl_vector`），得到 `(479,137, 978)` float32 ≈ 1.87 GB。

实现选项（按推荐顺序）：

1. **cmapPy**：`cmapPy.pandasGEXpress.parse_gctx(..., rid=landmark_ids, cid=needed_ids)`。需要 Python 环境已安装 cmapPy；服务器红线禁止装依赖，因此需要在**独立临时 venv/容器**中运行，或由用户批准后在非生产环境安装。不要动 `~/miniconda3` 的生产环境。
2. **gctx 直接解析**：gctx 是 HDF5 格式；用 `h5py` 按行/列读取，避免 cmapPy 的整体解析。需要确认文件内部的 dataset 布局（行优先/列优先）与 gzip 压缩层；实施前做 1 GB 样本测试。
3. **退路**：如果 52.4 GB 下载/解析不可行，改用 GSE70138 Level3（13.54 GB，345,976 列）或 Level4（已做板级 z），但覆盖的化合物/细胞系与 GSE92742 不同，需重新评估。

### 4.3 派生层格式

```
<DATA_DIR>/derived/l3_v1/
├── l3_landmark.npy       # (n_instances, 978) float32，约 1.87 GB
├── instance_meta.csv     # inst_id, rna_plate, rna_well, pert_id, pert_iname,
│                         # pert_type, cell_id, dose, time, is_control
├── plate_index.npz       # plate -> control row indices / sample row indices
├── gene_symbols.csv      # 978 行，顺序与 L7a 一致
└── manifest.json
```

- 行顺序按 `inst_id` 或 `(rna_plate, rna_well)` 稳定排序；
- `is_control=1` 表示 `ctl_vector`；
- 不把原始 gctx 放进派生目录；临时文件在验证后删除（释放约 120 GB）。

## 5. Robust z 算法

### 5.1 公式与边界

对每个板 `p`、每个基因 `g`：

```
ctrl = {x[i,g] : i in plate p, is_control=1}
med[g] = median(ctrl)
mad[g] = median(|ctrl − med[g]|)
scale[g] = 1.4826 * mad[g]
z[i,g] = (x[i,g] − med[g]) / scale[g]     if scale[g] > eps
z[i,g] = 0                                  if scale[g] <= eps（并记录 warning）
```

- `eps` 建议 `1e-6`；MAD=0 的基因在该板记 0 或 NaN，需统一策略并在 `qc` 中计数。
- 对照数 < 3 的板：跳过该板或回退到细胞系级对照，**不要跨板借用**（会引入批次效应）；具体策略待人工确认。
- 对照类型：shRNA 用 `ctl_vector`；化合物用 `ctl_vehicle`；`ctl_untrt` 只作为参考，不默认混入。
- 不做额外的分位数归一化；论文口径就是 median/MAD。

### 5.2 实例→基因聚合

- `SignatureEngine` 期望 `(978, n_samples)`；每个 L3 实例是一个样本。
- 对每个基因的 shRNA 实例，可以：
  - **实例级**：直接把所有实例作为样本（论文口径，推荐用于 L7b）；
  - **hairpin 级**：按 `pert_id` 聚合（中位数/均值），减少同一 hairpin 的重复；
  - 两种口径的 `n_samples` 不同，必须在签名 JSON 中记录 `aggregation`。
- 默认建议：`instance` 口径；`hairpin` 作为可选项。

## 6. L3Provider 接口设计

```python
class L3Provider(IDataProvider):
    def __init__(self, root: str):
        self.meta = pd.read_csv(f"{root}/instance_meta.csv")
        self.matrix = np.load(f"{root}/l3_landmark.npy", mmap_mode="r")
        self._row = {inst: i for i, inst in enumerate(self.meta.inst_id)}
        # 预计算 plate -> control rows, sample rows
        ...

    def get_shrna_samples(self, gene_name): ...
    def get_expression_matrix(self, sig_ids): ...
    def get_gene_symbols(self): ...
    def get_drug_samples(self): raise NotImplementedError("L3 仅用于签名；药物打分走 L5")
    def get_drug_expression_matrix(self, sig_ids): raise NotImplementedError
    def get_lm_gene_indices(self): return np.arange(978, dtype=np.int32)
    def get_vehicle_samples_for_plate(self, plate_id):
        return self.meta[(self.meta.rna_plate == plate_id) &
                         (self.meta.pert_type == "ctl_vector")].inst_id.tolist()
    def list_available_genes(self): ...
    def get_drug_name_map(self): raise NotImplementedError
```

注意：

- `get_drug_samples` / `get_drug_name_map` 抛 `NotImplementedError` 会让 `DrugScorer` 在 L3 模式下不可用；上层必须显式组合“L3 签名 + L5 药物打分”，不要复用 `TaskQueue._build_provider` 的单 provider 逻辑（`backend/task_queue.py:36-40`）。
- 建议新增 `CompositeProvider` 或让 `TaskQueue` 接收 `signature_provider` 与 `drug_provider` 两个参数；这是 L7e 实施时的必要改动。
- `get_expression_matrix` 返回 `(978, n)`；内部按行读取 `l3_landmark.npy`，不要按列随机读。
- 元数据 `pert_type` 要区分 `trt_sh` / `trt_sh.cgs` / `trt_sh.css`；当前 L5 用 `startswith("trt_sh")`，建议保持一致。

## 7. 性能与容量估算

| 项目 | 估算 |
|---|---|
| 下载 Level3 gctx.gz | 52.4 GB；取决于服务器出口带宽（未实测） |
| 解压/解析临时空间 | 约 65 GB（12,328×1,319,138×4）+ 5–10 GB 余量 |
| 提取派生层 | 1.87 GB |
| 峰值磁盘 | 约 120 GB（下载 + 解压 + 派生） |
| 解析时间 | 1–3 小时（gzip/解析受限；需先做 1 GB 样本测试） |
| robust z 计算 | 479,137×978 ≈ 4.7×10^8 个值；按板分组，预计 1–5 分钟（56 核可用并行） |
| 单次 `get_expression_matrix` | 读取 n×978×4；n=10,000 约 39 MB，<0.1 s（热） |
| 内存峰值（派生层映射） | 1.87 GB + 批处理缓冲 |

对比 L5：L5 的 `_shrna_rank_matrix.dat` 404 MB、`_drug_median_matrix.npy` 74 MB；L3 派生层更大，但仍远小于 23 GB 原矩阵。

## 8. 迁移步骤

### 8.1 可行性 spike（建议先做）

1. 下载 1 GB 的 gctx 片段或完整文件的前若干块，验证 h5py/cmapPy 能读取、行/列顺序正确。
2. 选 VCAP 的 10 块板、10 个基因，提取 `trt_sh` + `ctl_vector`，计算 robust z。
3. 与 L5 的同基因签名对比：样本数、KS 分布、up/down 重叠；记录差异。
4. 产出 2–3 页报告，决定是否全量实施。

### 8.2 全量实施

1. 用户批准数据准备与临时目录；不要在生产目录写文件。
2. 下载、校验、提取、生成 `l3_v1`；记录 manifest。
3. 实现 `L3Provider` + `CompositeProvider`；单测使用合成小矩阵（不依赖 52 GB 数据）。
4. `DATA_PROVIDER=l3` 灰度；只对 5 个基因跑签名，比较 L3 vs L5 的 `n_samples/qc/up_down`。
5. 若启用 L3 作为默认：必须同时重跑 L3 的 LOHO 判档与 L4 的 null/FDR；不要沿用 L5 阈值。
6. 回滚：`DATA_PROVIDER=l5`，L3 派生层可保留或删除。
7. 清理临时 gctx（释放约 120 GB）。

## 9. 验收清单（实施时执行）

- [ ] 派生层形状/大小符合预期：`(n_instances, 978)` float32；shRNA+ctl_vector 行数 479,137（若只取 trt_sh* + ctl_vector）。
- [ ] `inst_info` 与派生层 `instance_meta.csv` 一一对应；板号/孔号/扰动类型无丢失。
- [ ] 每块 shRNA 板的 `ctl_vector` 数与 `inst_info` 一致；对照数 <3 的板被明确标记。
- [ ] robust z 单测：手工构造 1 块板、3 个对照、2 个基因，逐元素验证 median/MAD/1.4826。
- [ ] MAD=0、对照数不足、NaN 三种边界行为符合文档。
- [ ] `get_expression_matrix` 返回 `(978, n)`；`get_vehicle_samples_for_plate` 返回同板 `ctl_vector`。
- [ ] `L3Provider` 的药物方法明确抛 `NotImplementedError`；`CompositeProvider` 能同时提供 L3 签名与 L5 药物。
- [ ] 5 个基因的 L3 vs L5 签名对比报告（样本数、KS、up/down 重叠）。
- [ ] 全量数据准备时间/磁盘实测值写入交付说明。
- [ ] 不修改生产目录、不重启服务、不安装依赖到生产环境。

## 10. 工作量估算

| 工作 | 人日 |
|---|---|
| 可行性 spike（下载样本、解析、10 基因对比） | 2 |
| 全量下载/提取/校验 | 1–2（机器时间为主） |
| `L3Provider` + `CompositeProvider` + 单测 | 2–3 |
| robust z/边界/并行 + 验证 | 1–2 |
| 与 L3 判档/L4 的联调 | 2–3 |
| 文档/评审/清理 | 1 |
| **合计** | **9–13 人日**（不含 52 GB 下载等待） |

## 11. 待人工确认

1. **对照语义**：是否确认 shRNA 的同板对照用 `ctl_vector`（空载体），而不是 `ctl_vehicle`？这是本方案能否成立的前提。
2. 是否值得做：L3 的主要价值是复现论文的实例级口径，但无法保证数值对齐；如果产品目标是排序改善，是否优先 L7a/L7b？
3. 数据准备许可：是否允许在服务器临时目录下载 52.4 GB 并在独立 venv/容器中安装 cmapPy/h5py？红线禁止在生产环境装依赖，需明确边界。
4. 对照数 <3 的板：跳过、回退到细胞系级对照，还是标记为不可用？
5. 实例级 vs hairpin 级聚合，哪个作为默认？
6. 若全量不可行，是否接受 GSE70138 Level3（13.54 GB，345,976 列）作为替代？覆盖范围不同。

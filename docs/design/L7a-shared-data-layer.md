# L7a · 共享 L1000 landmark 数据层（设计文档）

- 状态：方案待人工确认（只出文档，未实施）
- 基线：LMNA `main` @ `315f965`
- 关联：L7b（实例级 XSUM）依赖本方案；cmap-l1000 为共同消费方

## 1. 结论摘要

把 `cmap_data/fast_matrix.npy`（12328 × 473647，float32，23.36 GB，按基因/行存储）离线转换成一个只含 978 个 landmark 基因、按签名/行存储的 memmap：

- 形状 `(473647, 978)`，dtype `float32`，C 顺序，大小 **1,852,907,064 B（1.73 GiB / 1.85 GB）**。
- 生成时只读 landmark 的 978 行，不需要扫完 23 GB；在 keji 服务器实测 gather 4.88 s + 转置 1.09 s + 落盘 0.39 s（热页缓存），冷盘预算 1–5 分钟。
- 读取侧把 `matrix[:, sig_idx]`（每次读 12328 行、只留 978 行）改成 `matrix[sig_idx, :]`，数据量降到 978/12328 = **7.9%**，并变成连续行读取。
- 现有 `get_expression_matrix` 按 5000 列一块实测 6.36–6.63 s；整库 473647 列外推 **10.0–10.5 分钟/遍**。换成新层后同一块实测 0.02 s（热缓存），整库预计 **2–5 秒**。
- LMNA 与 cmap 用一个共享读取模块；cmap 的 `/extract` 仍要返回 12328 维向量，不能直接切到 landmark 层，需保留旧矩阵作为兼容路径（见 §6.2）。

推荐：

1. 生成脚本放在 LMNA `scripts/build_landmark_memmap.py`，产物放共享数据目录（不提交仓库）。
2. LMNA `L5Provider` 通过环境变量 `LMNA_LANDMARK_MATRIX` 切换；默认仍走旧矩阵，验证通过后再改默认。
3. cmap 只把 landmark 层用于“打分/全库搜索”路径；`/extract` 与任意 12328 基因查询保留旧路径，或在确有需要时另建 23 GB 的签名优先全基因层。

## 2. 现状与证据

### 2.1 代码事实

- `backend/config.py:17-31`：`DATA_DIR` 默认 `<repo>/../cmap_data`；`MATRIX_PATH=fast_matrix.npy`；`N_GENES=12328`、`N_SIGS=473647`。
- `backend/l5_provider.py:42-47`：以 `(12328, 473647)` 形状打开 memmap。
- `backend/l5_provider.py:110-124`：`get_expression_matrix` 按 5000 列分块，`full_cols = self._matrix[:, idx_chunk]`（第 122 行）先把 12328×5000 个 float 读出来，再用 `self._lm_indices` 取 978 行。实际读取量是需要的 12.6 倍，且每行只读 20 KB 后跨 23 GB 跳到下一行，属于典型的跨步读。
- `backend/signature_engine.py:53-58`：构建 shRNA 排名缓存时同样按 5000 列调用上面的方法；`backend/signature_engine.py:25-26` 缓存文件约 404 MB。
- `backend/drug_median_cache.py:50-76`：构建药物中位数缓存时按 1000 个药物一批读取全部实例，同样走 `get_expression_matrix`。
- `backend/data_provider.py:27-37`：接口约定 `get_expression_matrix` 返回 `(978, n_sigs)`；本方案保持返回形状不变，只换底层存储。
- cmap-l1000 `app/core/matrix_store.py:55-83`：`get_column` / `get_columns` 也是 `self._matrix[:, idx]`；`app/core/matrix_store.py:85-98` 的 `get_batch_iterator` 每批读 12328×batch。`app/api/extract.py:67-68` 明确返回 12328 维向量。

### 2.2 服务器实测（keji，2026-10-17，只读）

| 项目 | 实测值 |
|---|---|
| 主机 | hello-PowerEdge-T640，56 vCPU，754 GB RAM，`/home` 6.1 TB 可用 |
| `fast_matrix.npy` | 23,356,480,864 B（=12328×473647×4） |
| 顺序读吞吐（`dd iflag=direct`，2 GB） | 459 MB/s |
| 当前方法读 5000 列（200000–205000） | 6.36 s |
| 当前方法读 5000 列（400000–405000） | 6.63 s |
| 外推整库一遍 | 10.0–10.5 min |
| 只取 978 行读同样 5000 列 | 0.02 s（热缓存） |
| 978 行整行 gather | 4.88 s（1.85 GB） |
| 转置成 `(473647, 978)` | 1.09 s |
| `np.save` 1.85 GB | 0.39 s |
| landmark 基因数 | 978（`pr_is_lm==1`） |
| 现有药物中位数缓存 | 74 MiB（978×19811），`_drug_names.csv` 19811 行 |

说明：报告原文“首次构建要几个小时”是在更慢的磁盘/更多随机读的条件下成立；在当前服务器上一次全库扫描约 10 分钟。本方案的价值不是把 10 分钟变成 0，而是把每次读取的数据量降到 7.9%、把跨步读变成连续读，并且让 L7b 的实例级计算可以在秒级完成。

## 3. 目标与非目标

### 3.1 目标

- 一份只读、可直接 mmap 的 landmark 矩阵，LMNA 与 cmap 共用。
- 生成过程离线、幂等、可校验、可回滚；不修改原始 `fast_matrix.npy`。
- 读取接口保持 `(978, n)`，不改变上层 `SignatureEngine` / `DrugScorer` 的调用方式。
- 为 L7b 提供“按签名连续读取”的基础。

### 3.2 非目标

- 不改变 z-score / MODZ 的数值含义；不重算表达值。
- 不把 978 个基因扩展到 12328；`/extract` 这类需要全基因的接口仍走原矩阵。
- 不在本任务中写业务代码或生成数据（本任务只出设计）。

## 4. 文件格式与目录布局

建议目录（与 `cmap_data` 同级，避免混入原始数据）：

```
<DATA_DIR>/derived/landmark_v1/
├── landmark_sigs.npy        # (473647, 978) float32, C order, 1.73 GiB
├── landmark_genes.csv       # 978 行：gene_id,gene_symbol,source_row
├── sig_ids.csv              # 473647 行：sig_id,source_col
├── manifest.json            # 版本、形状、校验和、构建时间
└── BUILD.lock               # 构建期间存在，成功后删除
```

### 4.1 `landmark_sigs.npy`

- 标准 NumPy `.npy`，头部自带 shape/dtype/order，避免额外的 shape 文件。
- `shape=(n_sigs, 978)`，`dtype='<f4'`（小端 float32），C 顺序。
- 行顺序 = `col_sig_ids.csv` 的原始顺序；列顺序 = `landmark_genes.csv` 的顺序。
- 不写 NaN/Inf；构建时抽样校验。

### 4.2 `landmark_genes.csv`

| 列 | 含义 |
|---|---|
| `gene_id` | Entrez ID，与 `row_gene_ids.csv` 一致 |
| `gene_symbol` | `pr_gene_symbol`，供 `get_gene_symbols()` 返回 |
| `source_row` | 该基因在 12328 行矩阵中的原始行号 |

顺序必须与 `gene_info` 中 `pr_is_lm==1` 的原顺序一致（与当前 `l5_provider.py:61-72` 一致），这样现有签名数值不变。

### 4.3 `sig_ids.csv`

| 列 | 含义 |
|---|---|
| `sig_id` | 与 `col_sig_ids.csv` 完全一致 |
| `source_col` | 原矩阵列号（0-based） |

`source_col` 只用于校验和迁移排查；新层行号即数组下标。

### 4.4 `manifest.json`

```json
{
  "format": "l1000-landmark-memmap",
  "version": 1,
  "built_at_utc": "2026-10-17T00:00:00Z",
  "builder": "scripts/build_landmark_memmap.py",
  "shape": [473647, 978],
  "dtype": "<f4",
  "n_landmark": 978,
  "n_sigs": 473647,
  "source": {
    "matrix": {"path": "fast_matrix.npy", "size": 23356480864, "mtime_ns": 0},
    "gene_info_sha256": "...",
    "row_names_sha256": "...",
    "col_names_sha256": "..."
  },
  "checksums": {
    "landmark_sigs_sha256": "...",
    "landmark_genes_sha256": "...",
    "sig_ids_sha256": "..."
  }
}
```

校验和可选（1.85 GB 的 SHA256 约数秒）；至少记录源文件 size+mtime 与行/列名文件哈希，用于缓存失效判断（与 L2 的版本化衔接）。

## 5. 生成流程

### 5.1 步骤

1. 读 `gene_info`、`row_gene_ids.csv`，取 `pr_is_lm==1` 的 978 个基因；断言唯一、全部能在 `row_gene_ids` 中找到；得到 `lm_idx`（int32，978）。
2. 读 `col_sig_ids.csv`，断言 473647 个 `sig_id` 唯一。
3. 以只读方式 mmap `fast_matrix.npy`，形状 `(12328, 473647)`。
4. `X = np.asarray(mm[lm_idx, :])`，得到 `(978, 473647)` float32（1.85 GB）。这一步只读 978 行、每行 1.85 MB 连续数据，不读其余 11350 行。
5. 抽样检查 `np.isfinite(X)`（例如随机 1000 个元素）；如发现非有限值，记录并中止（或按既定策略置 0，需人工确认）。
6. `Y = np.ascontiguousarray(X.T)`，得到 `(473647, 978)`；峰值内存约 3.7 GB（服务器 754 GB，无压力）。
7. 用 `np.lib.format.open_memmap(tmp_path, mode='w+', dtype='<f4', shape=Y.shape)` 按行块写入（例如每块 50000 行，约 196 MB），`flush()` + `os.fsync()`，再 `os.replace()` 原子改名。
8. 写 `landmark_genes.csv`、`sig_ids.csv`；最后写 `manifest.json`（manifest 最后写，保证“有 manifest 即完整”）。
9. 校验：重新 mmap 新文件，随机抽 1000 个 `sig_id`，与旧路径 `mm[:, col][lm_idx]` 比较，要求逐元素完全相等（float32 原样拷贝，不是近似）。
10. 删除临时文件；保留 `BUILD.lock` 之外的旧文件不动。

### 5.2 参考实现骨架（仅文档，不在本任务提交）

```python
# scripts/build_landmark_memmap.py（示意）
import argparse, json, os, tempfile
import numpy as np, pandas as pd

def build(data_dir, out_dir):
    gene_info = pd.read_csv(f"{data_dir}/GSE92742_Broad_LINCS_gene_info.txt.gz", sep="\t")
    row_names = pd.read_csv(f"{data_dir}/row_gene_ids.csv")
    col_names = pd.read_csv(f"{data_dir}/col_sig_ids.csv")
    g2r = {g: i for i, g in enumerate(row_names["gene_id"])}
    lm = gene_info[gene_info["pr_is_lm"] == 1].reset_index(drop=True)
    lm_idx = np.array([g2r[g] for g in lm["pr_gene_id"]], dtype=np.int32)
    assert len(lm_idx) == 978 and len(set(lm_idx)) == 978

    src = np.memmap(f"{data_dir}/fast_matrix.npy", dtype="float32",
                    mode="r", shape=(12328, len(col_names)))
    X = np.asarray(src[lm_idx, :])              # (978, n_sigs)
    Y = np.ascontiguousarray(X.T)               # (n_sigs, 978)

    os.makedirs(out_dir, exist_ok=True)
    tmp = f"{out_dir}/landmark_sigs.npy.tmp"
    out = np.lib.format.open_memmap(tmp, mode="w+", dtype="<f4", shape=Y.shape)
    step = 50000
    for s in range(0, Y.shape[0], step):
        out[s:s+step] = Y[s:s+step]
    out.flush(); del out
    os.replace(tmp, f"{out_dir}/landmark_sigs.npy")
    # 写 csv / manifest ...
```

## 6. 消费端接口与改法

### 6.1 共享读取模块（建议新增 `backend/landmark_store.py`）

```python
class LandmarkStore:
    def __init__(self, root: str):
        self.root = root
        self.sig_ids = pd.read_csv(f"{root}/sig_ids.csv")["sig_id"].tolist()
        self._sig_index = {s: i for i, s in enumerate(self.sig_ids)}
        genes = pd.read_csv(f"{root}/landmark_genes.csv")
        self.gene_symbols = genes["gene_symbol"].tolist()
        self.matrix = np.load(f"{root}/landmark_sigs.npy", mmap_mode="r")

    def get(self, sig_ids, out=None):
        idx = [self._sig_index[s] for s in sig_ids]
        data = self.matrix[idx, :]              # (n, 978) 连续行
        return np.ascontiguousarray(data.T)     # (978, n)

    def get_gene_symbols(self):
        return list(self.gene_symbols)
```

要点：

- 缺 `sig_id` 时抛出带明确信息的 `KeyError`（与当前 `l5_provider.py:114` 的行为一致）。
- 去重/保序：上层若传入重复 `sig_id`，保持原顺序返回重复列。
- `out` 参数可选，便于调用方复用缓冲；默认返回新数组。
- 不要在每次请求时 `np.load` 整个文件；`mmap_mode='r'` 只映射，页缓存由 OS 管理。

### 6.2 LMNA `L5Provider` 改法

- 在 `__init__` 中：
  - 若环境变量 `LMNA_LANDMARK_MATRIX` 非空且目录存在：`self._store = LandmarkStore(...)`，`self._matrix = None`。
  - 否则保持现有 `np.memmap` 逻辑。
- `get_expression_matrix`：新路径直接 `return self._store.get(sig_ids)`；旧路径保留，便于回滚。
- `get_gene_symbols`：新路径返回 `self._store.get_gene_symbols()`；旧路径不变。
- `get_lm_gene_indices`：新路径返回 `np.arange(978, dtype=np.int32)`（新层已经是 landmark-only，接口语义从“原矩阵行号”变为“landmark 层行号”）；必须在接口 docstring 中注明，并检查唯一调用方。当前调用方是 `l5_provider.py` 自身与测试；`data_provider.py:72-80` 的抽象接口需要同步更新说明。
- `get_drug_expression_matrix`：委托 `get_expression_matrix`，不变。
- `_lm_gene_ids` / `_lm_indices` 在新路径不再需要构建（可保留空属性以避免外部访问报错）。
- 其余 shRNA/drug 元数据逻辑不变。

### 6.3 cmap-l1000 改法

cmap 有两种消费方式，必须分开处理：

1. **全库打分 / WTCS**（`app/api/wtcs_search.py`、`app/core/matrix_store.py:85-98`）：
   - 新增 `get_landmark_batch_iterator(batch_size=10000)`，从 landmark 层按行读取并转置成 `(978, batch)`。
   - 仅当查询基因全部落在 978 landmark 内时启用；否则回退旧的全基因矩阵。注意：这会改变“只用查询中可用基因”的集合，必须在响应里返回 `used_gene_count` 与 `fallback_reason`，避免静默改变结果。
2. **`/extract` 返回 12328 维向量**（`app/api/extract.py:67-68`）：
   - 必须继续读旧矩阵。若希望 `/extract` 也变快，可另建一个“签名优先、全 12328 基因”的 23.36 GB 层（`(473647, 12328)`），生成方式相同但内存峰值约 46 GB；这不是本方案的最小交付，列为可选第二阶段。

建议共享方式：两个项目都通过 `LandmarkStore` 读取同一个目录；仓库里只提交读取代码，不提交数据。数据目录用环境变量（LMNA `LMNA_LANDMARK_MATRIX`，cmap 新增 `CMAP_LANDMARK_MATRIX`）指向同一路径。

## 7. 迁移步骤

1. **离线构建**：在 keji 的临时目录生成 `landmark_v1`（不写 `~/cmap/cmap_data`，不改生产文件）；预计 1–5 分钟 + 1.85 GB 磁盘。
2. **数值校验**：随机 1000 个 `sig_id`，新旧路径逐元素相等；再抽 10 个 shRNA 基因的完整签名，比较 `up_genes/down_genes/ks_scores`（应完全一致）。
3. **灰度**：LMNA 设置 `LMNA_LANDMARK_MATRIX=<path>` 启动，跑 `/api/health`、`/api/genes/LMNA/compute`、`/api/genes/LMNA/drugs`；对比响应时间。
4. **默认切换**：灰度稳定一个发布周期后，把新路径设为默认；旧矩阵只读保留，作为回滚路径。
5. **cmap**：先只接 WTCS 的 landmark fast path；`/extract` 不动。上线前用 100 个随机查询对比新旧 WTCS 排名，确认差异只来自基因集合变化并记录。
6. **缓存失效**：与 L2 一起，把数据层版本（manifest 的 `version` + 源文件哈希）加入签名/药物缓存 key；旧缓存不能跨版本复用。
7. **回滚**：清空 `LMNA_LANDMARK_MATRIX` 环境变量并重启 API，即回到旧矩阵；不需要删新文件。

## 8. 性能与容量估算

| 场景 | 当前 | 新层 | 说明 |
|---|---|---|---|
| 读 5000 个签名 | 6.36–6.63 s | 0.02 s（热）/ 约 0.2–0.5 s（冷） | 246 MB → 19.6 MB |
| 扫描全部 473647 签名 | 10.0–10.5 min | 2–5 s（热）/ 约 5–10 s（冷） | 23.36 GB → 1.85 GB |
| shRNA 排名缓存构建（216081 签名） | 约 4.6 min（按 10 min × 45.6%） | 约 1–3 s | 不含排名计算 |
| 药物中位数缓存构建（205034 实例） | 约 4.3 min | 约 1–3 s | 不含 median 计算 |
| 磁盘 | 23.36 GB | +1.85 GB | 原始文件保留 |
| 构建内存峰值 | — | 约 3.7 GB | 978×473647 float32 ×2 |
| 读取内存 | 每 5000 列约 246 MB | 每 5000 列约 19.6 MB |  |

注意：新层的收益主要来自“不再读 11350 个非 landmark 行”。如果上层仍然按列随机访问，收益会打折；因此 `LandmarkStore.get` 必须按行取。另请注意页缓存：1.85 GB 在服务器 754 GB 内存中很容易常驻，第二次查询接近内存速度。

## 9. 验收清单（实施时执行）

- [ ] 产物形状/类型/字节数精确为 `(473647, 978)`、`<f4`、1,852,907,064 B。
- [ ] `landmark_genes.csv` 978 行、`sig_ids.csv` 473647 行、无重复。
- [ ] 随机 1000 个 `sig_id` 新旧逐元素相等（`np.array_equal`，不是 allclose）。
- [ ] 10 个基因的签名 JSON（up/down/ks）新旧一致。
- [ ] `get_expression_matrix` 返回 `(978, n)`，重复/乱序 `sig_id` 行为与旧实现一致。
- [ ] 不存在的 `sig_id` 抛出的异常类型/信息与旧实现等价（或明确改进并记录）。
- [ ] 构建中断不会留下可被误用的半成品（manifest 最后写 + 原子 rename）。
- [ ] 旧路径可通过环境变量回滚，且回归测试通过。
- [ ] cmap 的 `/extract` 行为不变；WTCS fast path 在查询含非 landmark 基因时正确回退。
- [ ] 性能记录：5000 签名读取时间、全库扫描时间、构建时间，写入交付说明。

## 10. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| landmark 行顺序与 `gene_info` 不一致 | 签名数值整体错位 | 以 `gene_info` 的 `pr_is_lm` 原顺序为准；构建时断言 978 个唯一行；新旧数值校验 |
| `sig_id` 顺序与 `col_sig_ids.csv` 不一致 | 药物/签名错配 | 行顺序直接复制 `col_sig_ids.csv`；`source_col` 校验 |
| 构建时读到非有限值 | 打分出现 NaN | 抽样检查；发现即中止并报告，不静默替换 |
| cmap `/extract` 被误切到 landmark 层 | 返回维度从 12328 变 978，破坏 API | 明确禁止；`/extract` 保留旧路径；代码评审检查 |
| 共享目录权限/路径不一致 | 两个项目读到不同版本 | manifest 版本 + 环境变量；启动时校验 shape 和 manifest |
| 磁盘空间 | 构建失败 | 预留 5 GB；临时文件与正式文件同目录，原子 rename |
| float32 精度 | 与旧数据不一致 | 不做任何数值转换，直接拷贝 float32；校验用 `array_equal` |

## 11. 工作量估算

| 工作 | 人日 |
|---|---|
| 生成脚本 + 校验脚本 | 0.5 |
| `LandmarkStore` + LMNA `L5Provider` 改造 + 测试 | 0.5–1 |
| cmap WTCS fast path + 回退逻辑 + 测试 | 0.5–1 |
| 部署/灰度/回滚文档 | 0.25 |
| **合计（最小交付）** | **1.75–2.75 人日** |
| 可选：全基因签名优先层（23.36 GB） | +1 人日 + 23.36 GB 磁盘 |

## 12. 待人工确认

1. 共享数据目录的最终位置：`<DATA_DIR>/derived/landmark_v1/` 还是服务器上的独立共享目录（两个项目都能读）？
2. cmap 是否接受“WTCS 仅 landmark 查询走快路径、混合查询回退”的语义？如果不接受，是否愿意承担 23.36 GB 的全基因签名优先层？
3. 是否把 `get_lm_gene_indices` 的语义改为 landmark 层行号（0..977）？这会影响接口文档与潜在外部调用。
4. 是否需要在 manifest 中加入完整 SHA256（构建时间增加数秒）？
5. 是否把该层作为 L7b 的强依赖先行实施（推荐是）。

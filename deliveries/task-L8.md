# task-L8 · LMNA 数据层列序对齐 + 缓存重建方案

任务ID / 分支 / 基线提交：`L8` / `fix/L8-col-order` / `origin/main` @ `3b799ee`（含 L1 合并提交）

## 结论摘要

1. **真值来源已确认**：`fast_matrix.npy` 的列序 = `GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx` 的 `0/META/COL/id` 顺序；行序 = 同一 GCTX 的 `0/META/ROW/id` 顺序。服务器只读抽样核对 `fast_matrix[:, k] == gctx[k, :]`，`max|diff| = 0.0`。
2. **采用方案 A**：用 `scripts/fix_col_names.py` 重新生成与矩阵列同序的 `col_sig_ids.csv`，`L5Provider` 的列映射逻辑不变；另加一个 fail-fast 哨兵，拒绝旧的“字典序”文件，避免部署顺序错误时静默读错。
3. **额外 P0 发现（任务要求只查不修）**：`row_gene_ids.csv` 与矩阵**行序同样错位**。`row_gene_ids.csv` 是 `gene_info` 文件顺序，矩阵行序是 GCTX ROW 顺序，12328 个位置仅 4 个相同，978 个 landmark 基因位置 **0 个相同**。只修列序后，`get_expression_matrix` 的 978 维向量仍与 GCTX 真值近似不相关（r ≈ 0.003 / −0.002 / −0.016）。脚本提供可选的 `--fix-rows`（默认关闭），**上线时必须显式决定是否执行**，否则验收 1/3/4 在生产上不成立。
4. **cmap 侧同病**：`metadata_index` 用同一个 `COL_NAMES_PATH` 建 `sig_id -> 列索引`；`search/export/tau_search/wtcs_search` 用 `ROW_NAMES_PATH` 建 `gene_id -> 行索引`。本任务未改 cmap 仓库。

## 改动文件（文件:行号范围）

| 文件 | 行号 | 改动 |
|---|---|---|
| `backend/l5_provider.py` | 21-24 | 新增 `CHECK_COL_ORDER` 哨兵开关 |
| `backend/l5_provider.py` | 56-67 | 列名读取增加行数校验 + “全字典序”旧文件 fail-fast 拒绝；`_sig_id_to_idx` 逻辑本身不变（方案 A） |
| `backend/tests/test_l8_col_order.py` | 1-183（新增） | 6 项 L8 验收测试 |
| `backend/tests/data/l8_col_order_slice.npz` | 新增，26,350 B | 真实 GCTX 真值切片：4 sig_id（2 trt_cp + 2 trt_sh）× 978 landmark |
| `scripts/fix_col_names.py` | 新增 | 方案 A：按 GCTX COL 顺序重生成 `col_sig_ids.csv`；只读诊断行序；可选 `--fix-rows` |
| `scripts/verify_drug_median.py` | 新增 | 部署后人工复核缓存与 GCTX/beta 真值的相关性 |
| `deliveries/task-L8.md` | 新增 | 本文件 |

## 采用的方案（A 重生成 col_sig_ids.csv / B 直读 GCTX cid）及理由

**选择 A（重生成 `col_sig_ids.csv`）**。

理由：

- 任务推荐 A；改动面最小。矩阵列序本来就是 GCTX COL 顺序，错的只是同名 CSV 的语义。
- `col_sig_ids.csv` 是 `~/cmap/cmap_data` 下的共享数据文件，cmap 与 LMNA 都读它；修一次两边同时受益（cmap 重启后生效）。
- 运行时不需要引入 `h5py` 依赖，也不需要把 GCTX 路径写进 LMNA 配置；方案 B 需要在每次进程启动时读 473,647 个列 id，且只修 LMNA、不修 cmap。
- 为防止“代码已上线但数据文件还没替换”时静默读错，`L5Provider` 增加哨兵：473,647 个 GCTX 列 id 恰好完全字典序的概率可忽略，检测到全排序即抛 `RuntimeError` 并提示先跑脚本。测试可用 `l5_provider.CHECK_COL_ORDER = False` 复现旧行为。

`scripts/fix_col_names.py` 的能力：

```bash
# 只检查（不写文件）
python scripts/fix_col_names.py --check

# 生成 col_sig_ids.fixed.csv，人工确认后再替换
python scripts/fix_col_names.py --data-dir ~/cmap/cmap_data

# 原地替换（自动备份 col_sig_ids.csv.bak-<时间戳>）
python scripts/fix_col_names.py --data-dir ~/cmap/cmap_data --in-place

# 追加修复行序（L8 额外发现；默认关闭，见下文）
python scripts/fix_col_names.py --data-dir ~/cmap/cmap_data --in-place --fix-rows
```

真实数据只读运行结果（`--check`，本地与服务器同 md5 的数据副本）：

```text
col_sig_ids.csv: 473647 行，GCTX 元数据 473647 行
  同位置一致: 3/473647；集合相同: True
  首个不一致位置: 0；文件='AML001_CD34_24H:A05'，GCTX='CPC005_A375_6H:BRD-A85280935-003-01-7:10'
row_gene_ids.csv: 12328 行，GCTX 元数据 12328 行
  同位置一致: 4/12328；集合相同: True
  首个不一致位置: 0；文件='780'，GCTX='5720'
抽样列校验（fast_matrix[:, k] vs GCTX[k, :]）：
  [OK] k=0 ... max|diff|=0.000e+00
  [OK] k=236823 ... max|diff|=0.000e+00
  [OK] k=473646 ... max|diff|=0.000e+00
```

生成的正确文件：473,647 行、无重复、首项 `CPC005_A375_6H:BRD-A85280935-003-01-7:10`、末项 `PCLB003_PC3_24H:BRD-K04466929-001-05-1:10`、非字典序（md5 `9da43276fd375979f9e5e400ef42d00b`）。

## 测试：新增测试、pytest 输出、修复前失败 → 修复后通过

新增 `backend/tests/test_l8_col_order.py`（6 项）：

| 测试 | 内容 |
|---|---|
| `test_fixture_covers_cp_and_sh` | 夹具至少 3 个 sig、含 trt_cp 与 trt_sh |
| `test_fixed_col_names_match_gctx_truth` | **验收 1**：3 个 sig（含 cp/sh）978 维向量 vs GCTX 真值，max abs diff < 1e-5 |
| `test_all_four_sigs_match_gctx_truth` | 4 个 sig 全部逐元素一致 |
| `test_sorted_col_names_are_rejected` | **验收 2a**：旧排序文件触发 `RuntimeError`（fail-fast） |
| `test_sorted_col_names_read_wrong_columns` | **验收 2b**：关闭哨兵后复现旧行为，两个 vorinostat cp 列被互换，与真值明显不一致 |
| `test_drug_median_rebuilt_from_fixed_provider` | **验收 3**：用修复后的 provider 重建药物中位数，vorinostat 的 978 维向量与真值 `r = 1.0`、max abs diff < 1e-5 |

夹具说明：`l8_col_order_slice.npz` 是从 GSE92742 Level5 GCTX 抽取的**真实数值**（4 个 sig × 978 landmark，26 KB）；列顺序取这 4 个 sig 在完整 GCTX COL 中的相对顺序。测试里的 `row_gene_ids.csv` 使用**正确行序**，目的是隔离本任务的列序 bug；生产行序问题见下一节。

`pytest -q`（L8 专项）：

```text
tests/test_l8_col_order.py ......                                        [100%]
6 passed in 1.12s
```

`pytest -q`（全量，`LMNA_FIXTURE_DIR=D:\agent-workspace\deliveries\task-L0\fixtures`）：

```text
51 passed, 1 skipped, 4 warnings in 11.86s
```

`pytest -q`（全量，不设夹具）：`27 passed, 25 skipped in 2.57s`（L8 测试自带 26 KB 夹具，不依赖 L0 夹具）。

**修复前失败 / 修复后通过的证据**：

- 真实数据逐列核对（`deliveries/task-L8/real_data_check.json`）：旧排序映射的完整 12328 维列与 GCTX 真值 `max|diff|` 分别为 12.51 / 5.54 / 5.17；改用 GCTX COL 顺序后三者均为 **0.0**。
- 夹具测试：旧排序映射导致两个 cp 列互换（`got[:,0] == truth[:,1]`、`got[:,1] == truth[:,0]`），`max|diff| > 1e-3`；修复后 `max|diff| < 1e-5`。
- 哨兵：旧排序文件直接 `RuntimeError`，不会再静默返回错误签名。

## 行顺序排查结论（`row_gene_ids.csv` 是否也有问题）

**是，同样错位，而且同样严重。** 任务要求“只查不修”，本任务未改 `L5Provider` 的行映射，也未默认改数据文件。

证据（本地副本与服务器文件 md5 完全一致，服务器只读复核）：

- `row_gene_ids.csv` 与 GCTX `0/META/ROW/id`：集合相同，但同位置仅 **4/12328**；文件第 0 项 `780`（= `gene_info` 第 0 行），GCTX ROW 第 0 项 `5720`。
- `row_gene_ids.csv` 与 `GSE92742_Broad_LINCS_gene_info.txt.gz` 的 `pr_gene_id` 顺序**完全一致**（说明它是按 gene_info 文件顺序生成的，不是按矩阵行序）。
- 978 个 landmark 基因在两种顺序中的位置：**0/978 相同**。
- 只修列序、不改行序时，3 个已知 sig 的 `get_expression_matrix` 978 维向量与 GCTX 真值相关系数：**0.0032 / −0.0018 / −0.0161**（近似不相关），max abs diff 3.9–15.5。
- 影响点：`backend/l5_provider.py:71-88` 用 `row_gene_ids.csv` 建 `gene_id -> row` 并计算 `_lm_indices`，而矩阵行序是 GCTX ROW 顺序；`get_expression_matrix` 的 978 行因此取到错误基因，药物中位数缓存也会整行错位。

**结论**：只执行方案 A 上线，`_drug_median_matrix.npy` 重建后仍然不可信；验收 1/3/4 只有在行序也修正后才成立。`scripts/fix_col_names.py --fix-rows` 提供了现成修复（GCTX ROW 顺序、自动备份），默认关闭以遵守“只查不修”；**是否在本次上线执行，需要 🧑‍⚖️ 决策（强烈建议执行）**。

## cmap 侧是否同病（排查结论，本任务不改 cmap）

**是，列序和行序都同病。** 只读代码核对（`D:\agent-workspace\repos\cmap-l1000`）：

- 列序：`app/core/metadata_index.py:68-77` 的 `_build_sig_index()` 用 `COL_NAMES_PATH` 建 `sig_id -> idx`；`app/core/matrix_store.py:55-70` 直接用该 idx 取列。与 LMNA 完全相同的错误映射。
- 行序：以下位置都用 `ROW_NAMES_PATH` 建 `gene_id -> 行索引`，而矩阵行序是 GCTX ROW 顺序：
  - `app/api/search.py:47-54`
  - `app/api/export.py:53-60`
  - `app/api/export_wtcs.py:45-52`
  - `app/api/tau_search.py:54-61`
  - `app/api/wtcs_search.py:45-52`
  查询向量会把 up/down 基因写到错误的矩阵行，余弦/Tau/WTCS 打分随之错误。
- 因此 cmap 的 C1/C3/C4/C5 结果都受影响；修复共享的 `col_sig_ids.csv`（方案 A）并重启 cmap 后列序恢复，行序仍需同一份 `row_gene_ids.csv` 修复（`--fix-rows`）。
- 本任务未修改 cmap 仓库、未在服务器上改动/重启 cmap。

## 上线步骤（供人执行）

> 红线：本任务未在服务器改任何文件、未删缓存、未重启服务。以下全部由人在部署窗口执行。

1. **备份并修列序（必须）**
   ```bash
   cd ~/LMNA   # 或代码部署目录，确保 scripts/ 已随分支上线
   python scripts/fix_col_names.py --check --data-dir ~/cmap/cmap_data
   python scripts/fix_col_names.py --data-dir ~/cmap/cmap_data --in-place --fix-rows
   ```
   - `--fix-rows` 是本次额外发现的行序修复；若决定不执行，LMNA/cmap 的 978 维表达向量仍会错（见上节）。
   - 脚本自动生成 `col_sig_ids.csv.bak-<时间戳>`、`row_gene_ids.csv.bak-<时间戳>`。
   - 替换后再次 `--check`，应显示 `col_sig_ids.csv` 与 `row_gene_ids.csv` 均 `[OK] 顺序一致`。
2. **删旧缓存（与 L1/L2 联动）**
   ```bash
   rm -f ~/LMNA/cache/_drug_median_matrix.npy ~/LMNA/cache/_drug_names.csv
   rm -rf ~/LMNA/cache/signatures ~/LMNA/cache/drug_scores ~/LMNA/cache/tasks
   rm -f ~/LMNA/cache/_shrna_rank_matrix.dat ~/LMNA/cache/_shrna_rank_shape.txt
   ```
   说明：`_drug_median_matrix.npy`/`_drug_names.csv` 是 L8 的直接产物；其余是 L1 上线要求的旧缓存。L2 的缓存版本化会兜底强制失效。
3. **重启 LMNA 服务**（代码部署后）。`L5Provider` 启动时会检查 `col_sig_ids.csv`：若仍是排序文件会直接 `RuntimeError`，这是有意的 fail-fast。若 cmap 与 LMNA 共用 `~/cmap/cmap_data`，cmap 也需重启/重建其内存索引。
4. **首次查询触发重建**（或按部署脚本预热），然后人工复核：
   ```bash
   python scripts/verify_drug_median.py --n-drugs 5
   # 可选：与 LINCS2020 beta Level5 做趋势对照
   python scripts/verify_drug_median.py --n-drugs 5 --beta-dir /data2/wanggang/camp/level5
   ```
   - 默认真值 = 缓存来源 GSE92742 Level5，修复正确时 r 应 ≥ 0.99；低于阈值脚本返回 1。
   - `--beta-dir` 是不同数据集，r 只作趋势参考，不设硬阈值。
   - 脚本会先打印行序诊断；若显示 `row_gene_ids.csv` 与 GCTX ROW 不一致，说明行序未修，缓存仍不可信。
5. **验收 4 的最终数字**：部署重建后由人运行上述脚本，把 `r` 从 ≈0 提升到 ≥0.99 的结果回填到本文件/发布说明。

## 待人工确认（🧑‍⚖️）

1. **行序修复是否纳入本次上线**：任务原文对 `row_gene_ids.csv` 是“只查不修”，但实测不修行序时验收 1/3/4 在生产不成立。建议本次直接执行 `--fix-rows`（脚本已提供、自动备份、可回滚）；若坚持只修列序，则应把行序另开 P0 任务，并暂缓 L2–L6/C3 上线。
2. **cmap 是否同步上线**：修共享 CSV 会改变 cmap 的 `sig_id -> 列` 与 `gene_id -> 行` 语义，cmap 需要重启以重建索引；是否与 LMNA 同窗口执行，需协调。
3. **最终复核阈值**：验收 4 写的是“与 beta 真值相关系数提升”，但缓存数据源是 GSE92742。本脚本默认用 GSE92742 真值（应 ≈1.0），beta 仅作趋势对照；若要以 beta 为硬阈值，需要确认可接受的 r 范围。
4. **`CHECK_COL_ORDER` 哨兵**：是否保留为长期保护（每次启动多一次 473k 字符串排序，约百毫秒级）；若担心误伤，可改为仅在检测到文件 mtime/size 异常时警告。

## 发现但未处理

1. **`row_gene_ids.csv` 行序错位**：已排查、已提供 `--fix-rows` 工具，但按任务要求默认不修改；这是 L8 之后仍存在的生产正确性风险（见上）。
2. **cmap 同病**：未改 cmap 仓库；`metadata_index`、`search/export/tau/wtcs` 的映射问题需由 cmap 任务（C3 等）或单独任务处理。
3. **`col_sig_ids.csv` 的生成脚本不在仓库内**：无法追溯当年为何按字典序导出；建议后续把“数据文件生成/校验”纳入部署流水线（本任务只补了修复与校验脚本）。
4. **`fix_col_names.py` 依赖 `h5py`**：仅部署时使用，未加入 LMNA 运行时 `requirements.txt`；服务器 cmap conda 环境已具备。
5. **未在服务器重建缓存**：按红线由人执行；`verify_drug_median.py` 已用本地构造的正确/行错位缓存做过冒烟（正确 r=1.0000，行错位 r=0.0933、退出码 1）。
6. **服务器只读核对**：`col_sig_ids.csv` md5 `a55b1e318fb1267ef5c7e35efeac7c49`、`row_gene_ids.csv` md5 `1365df63dd2decb0161cef5925a9ee07`；与本地 `D:\mine_python_project\CMAP\cmap_data` 完全一致，故本地复现可直接代表生产数据。

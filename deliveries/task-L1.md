# task-L1 · LMNA 签名与打分算法修复

任务ID / 分支 / 基线提交：`L1` / `fix/L1-ks-sign` / `origin/main` @ `18685fe`（L0 合并提交）

## 符号约定（严格按任务文件，未自行定义）

| 量 | 约定 |
|---|---|
| 样本内秩 | 1 = 表达最高，G = 最低（G 由数据推导，不再写死 978） |
| KS 分数 | **KS > 0 = 敲低后该基因上调 → `up_genes`；KS < 0 → `down_genes`** |
| XSUM 原始量 | `mimic = Σz(up) − Σz(down)`，正 = 药物模拟敲低 |
| 输出 `score` | **`score = −mimic`**，高分 = 逆转；`top_drugs` 降序 = 逆转药，`bottom_drugs` = 模拟/加重 |
| WTCS 型分数 | 公式符号**未改**（`−Σw_up + Σw_down`），只把 `G` 改为矩阵行数 |
| `mode` | `lof` 默认找逆转药（score 降序）；`gof` 找模拟药（升序）。本任务未新增 API 参数，仅沿用约定 |

## 改动文件（文件:行号范围）

| 文件 | 行号 | 改动 |
|---|---|---|
| `backend/signature_engine.py` | 37-40 | 秩缓存形状校验改为 `(len(provider.get_gene_symbols()), n_shrna)` |
| 同上 | 85-98 | KS 符号改为 `np.where(D_plus >= D_minus, D_plus, -D_minus)`；`G` 改为必传 |
| 同上 | 106-114 | 保存 shRNA 样本表（与秩矩阵列同序）与 `_n_genes` |
| 同上 | 132-157 | 观测 KS 传 `G`；按 `pert_iname` 计算目标基因列 `exclude_cols`；p 值改为 `(k+1)/(B+1)`，`B` 取 null 实际行数 |
| 同上 | 162-207 | 新增 `n_sig`（封顶前）；`MAX_GENES_PER_DIRECTION` 每方向按 KS 强度排序封顶；`fast_mode_used` 只在真正触发时置 True |
| 同上 | 209-224 | 返回新增 `n_sig`、`fast_mode`、`params` |
| 同上 | 226-267 | `_bootstrap_null_ks(..., exclude_cols)`：池 = 全部列去掉目标基因列；每次 `rng.choice(pool, n_sample, replace=False)`；`G` 取矩阵行数 |
| 同上 | 270-282 | 删除 BH 前向 cummin，只保留 `sorted_p * n / arange(1,n+1)` + 反向 cummin |
| `backend/config.py` | 44-56 | `MIN_SH_SAMPLES` 环境变量化（默认 3，D3 待确认）；新增 `MAX_GENES_PER_DIRECTION`（默认 50，0=不封顶）；`FAST_MODE_TOP_N` 默认改 `0` |
| 同上 | 71-83 | 新增 `signature_params()`（L2 会在此基础上加 `ALGO_VERSION`） |
| `backend/l5_provider.py` | 85-88 | `pert_type.str.startswith('trt_sh')` → `pert_type == 'trt_sh'`（排除 `trt_sh.cgs`） |
| 同上 | 120 | `np.empty((978, n))` → `(len(self._lm_gene_symbols), n)` |
| `backend/drug_scorer.py` | 55-61 | XSUM 改为 `score = −Σz_up + Σz_down`，仍按 score 降序 |
| 同上 | 98 | WTCS `G = self._drug_matrix.shape[0]`（符号未改） |
| `backend/drug_median_cache.py` | 69 | 中位数矩阵高度改为 `matrix.shape[0]` |
| `backend/main.py` | 18-21, 86 | `/status` 的 `available` 用 `config.MIN_SH_SAMPLES` |
| 同上 | 98-116 | `/compute`：`n==0` 仍 404；`0 < n < MIN_SH_SAMPLES` 返回 422，detail 含样本数与门槛 |
| 同上 | 152-166 | `/signature` 返回 `n_sig`、`fast_mode`、`params`（旧缓存有默认值） |
| `backend/task_queue.py` | 74-92 | 任务结果 `signature` 返回 `n_sig`、`fast_mode`、`params` |
| `backend/tests/test_core_pure.py` | 73-92 | 按新符号约定更新 KS 极值断言；BH 注释更新 |
| `backend/tests/test_signature_math.py` | 新增 | KS 符号、G 必传、BH vs scipy、噪声 BH、p 值下限、null 抽样、快速模式、封顶/n_sig、XSUM/WTCS、API、任务结果字段 |
| `backend/tests/test_fixture_regression.py` | 新增 | 夹具回归：靶基因在 down、参考 KS、Jaccard、XSUM 抑制剂百分位、Table S1 占位（无文件 skip） |

## 测试

`cd backend && pytest -q`（**无夹具**，未设置 `LMNA_FIXTURE_DIR`）：

```
ssss.........sssssssssssssssssss..........ss..                           [100%]
21 passed, 25 skipped in 1.78s
```

`LMNA_FIXTURE_DIR=D:\agent-workspace\deliveries\task-L0\fixtures pytest -q`：

```
..............................s...............                           [100%]
45 passed, 1 skipped, 4 warnings in 10.63s
```

（1 skipped = D3 Table S1 未提供；4 warnings 为 starlette/httpx 的弃用警告。完整日志在本地
`D:\agent-workspace\deliveries\task-L1\pytest_without_fixture.log` 与 `pytest_with_fixture.log`。）

### 夹具回归实测（BOOTSTRAP_N=1000、FDR<0.05、|KS|>0.2、每方向封顶 50）

| 靶点 | 观测 KS（参考） | n_sig | up/down | 靶基因在 down | 抑制剂最低分百分位（参考） |
|---|---|---|---|---|---|
| CDK4 | **−0.7457**（−0.746） | 234 | 50 / 50 | 是 | 0.9908（0.994） |
| TOP2A | **−0.8374**（−0.837） | 95 | 42 / 50 | 是 | 0.9997（1.0） |
| EGFR | **−0.5282**（−0.460） | 37 | 14 / 23 | 是 | 0.9949（0.973） |

EGFR 的 KS 与论文参考差 0.068：夹具取的是前 150 个 EGFR shRNA 样本（15 个 hairpin），
与论文样本集不同；符号、归属与量级均正确，测试容差设为 0.12。

## 验收逐条核对

任务原文 14 项：

- [x] 1. KS 符号 `np.where(D_plus >= D_minus, D_plus, -D_minus)`；`test_ks_sign_upregulated_is_positive` / `test_ks_sign_downregulated_is_negative`、`test_core_pure.py::test_ks_uniform_batch_extremes`。
- [x] 2. p 值 `(k+1)/(B+1)`，B 取 null 实际行数；`test_p_values_never_zero_and_min_is_one_over_B_plus_1`。
- [x] 3. 删除 BH 前向 cummin；`test_bh_matches_scipy`（≤1e-12）、`test_bh_noise_plus_three_signals`（≤10 个）。
- [x] 4. `l5_provider.py:87` 改为 `pert_type == 'trt_sh'`（排除 `trt_sh.cgs`）。代码审查核对；L5Provider 需要服务器全量数据，未在本地实例化。
- [x] 5. `_bootstrap_null_ks` 新增 `exclude_cols`，池去掉目标基因列，每次 `choice(..., replace=False)`；`test_bootstrap_excludes_target_columns_and_samples_without_replacement`。
- [x] 6. `fast_mode_used` 实际触发才为 True，返回 `fast_mode` 与 `params`；`test_fast_mode_flag_reflects_actual_trigger`。
- [x] 7. `FAST_MODE_TOP_N` 默认 `0`；`config.py:56`。
- [x] 8. `MAX_GENES_PER_DIRECTION` 默认 50（0=不封顶），up 按 KS 降序、down 升序；`test_n_sig_counts_before_cap_and_cap_applies_per_direction`。
- [x] 9. 返回 `n_sig` = 封顶前通过 FDR+KS 的基因数；同上测试。
- [x] 10. XSUM 改为 `−Σz_up + Σz_down`，高分=逆转；`test_xsum_high_score_means_reversal` + 夹具抑制剂百分位。
- [x] 11. WTCS 符号未改，`G = self._drug_matrix.shape[0]`；`test_xsum_high_score_means_reversal` 中 inhibitor 仍排第一。
- [x] 12. `/status` 与 `/compute` 使用 `config.MIN_SH_SAMPLES`；`0<n<MIN` 返回 422；`test_api_status_and_compute_use_min_sh_samples`（临时设为 1000）。
- [x] 13. `/signature` 与任务结果都返回 `fast_mode`、`n_sig`、`params`；`test_signature_endpoint_returns_new_fields`、`test_task_result_contains_new_fields`。
- [x] 14. 写死的 978 全部改为数据推导：秩缓存形状、`ks_uniform_batch(G)` 必传、null 矩阵高度、L5 表达矩阵行数、药物中位数矩阵高度、WTCS `G`；`test_ks_uniform_batch_requires_G`。

验收清单：

- [x] KS 符号：978×20 构造，基因 0 全秩 1 → KS > 0.9。
- [x] BH vs scipy（含并列、含 1.0）最大绝对差 < 1e-12；975 噪声 + 3×1e-6 → q<0.05 个数 ≤10。
- [x] p 值无 0，最小 `1/(B+1)`。
- [x] null 抽样不含目标基因列、每次无重复。
- [x] 夹具回归 CDK4/TOP2A/EGFR：靶基因在 `down_genes`；Jaccard 检查（见下方说明）；XSUM 抑制剂百分位 ≥0.95；`FAST_MODE_TOP_N=0` 且无显著基因时 up/down 为空、`fast_mode=False`。
- [x] API：`/status` 与 `MIN_SH_SAMPLES` 一致；`MIN_SH_SAMPLES=1000` 时 `/compute` 返回 422。
- [x] D3 Table S1：未提供 `backend/tests/fixtures/table_s1.tsv`，对应测试 skip。

## 上线数据动作（必须执行）

修复上线后旧结果全部作废，必须清空：

- `cache/signatures/`、`cache/drug_scores/`、`cache/tasks/`；
- **另外必须删 `cache/_shrna_rank_matrix.dat`、`cache/_shrna_rank_shape.txt`**：`trt_sh.cgs` 被排除后 shRNA 池列集合已变化，旧排名缓存不可再用（形状校验通常会触发重建，但不应依赖它）。

`_drug_median_matrix.npy` 由 `trt_cp` 构建，本次过滤改动不影响；如无把握可一并删除后重建。

## 待人工确认（🧑‍⚖️）

- **D1（旧结论公告 / FDR 阈值）**：KS 符号翻转后，所有旧签名与药物排名结论作废，是否发布公告、是否需要保留旧结果对照，请用户决定。FDR/KS 阈值已做成环境变量：默认 `FDR_THRESHOLD=0.05` + `KS_THRESHOLD=0.2`；论文模式 `FDR_THRESHOLD=0.001` 需同时设 `BOOTSTRAP_N>=100000`（未改默认值，未替用户拍板）。
- **D3（样本门槛）**：`MIN_SH_SAMPLES` 已改为环境变量（默认仍为 3）。`n_shrna < 门槛` 时 `/compute` 返回 422 是否过硬、默认值是否应上调（如 422 相关口径），请用户确认。
- **D1（每方向封顶）**：`MAX_GENES_PER_DIRECTION` 默认 50 来自判档阈值校准；是否保持 50、还是设 0 不封顶，请用户确认。

## 发现但未处理

1. **严重（L0 遗留，超出 L1 14 项范围）**：`cmap_data/col_sig_ids.csv` 与 `fast_matrix.npy` 列顺序不一致（L0 实测 `fast[:,0] == gctx[0,:]`）。`L5Provider` 用 `col_sig_ids.csv` 建 `sig_id→列` 映射，生产环境会读到错误签名；服务器 `~/LMNA/cache/_drug_median_matrix.npy` 也可能由错误映射生成。**是否属于 L1**：14 项中没有列映射修复，且 L1 的算法与夹具回归全部走 `FixtureProvider`（其矩阵由 L0 直接按 GCTX COL 顺序重建），因此 L1 的 14 项验收不受该问题影响。**对验收的影响**：本地夹具可证明算法正确，但生产 L5 路径在修复列映射前仍不可信；L2 的缓存版本化也不会修复它。建议单开数据层任务，最小改法是按 GCTX 的 COL 顺序（或 sig_id 实际顺序）重新生成 `col_sig_ids.csv`，并在 `L5Provider.__init__` 加一致性校验（列数/抽样 sig_id 对照）。本次未扩大重构。
2. **L0 未保存夹具期望签名**：L0 交付说明建议重建时保存 `expected.json`，但夹具目录中没有该文件。L1 用修正后的算法、固定 `RANDOM_SEED=42`、`BOOTSTRAP_N=1000`、每方向 50 生成了 `lmna_fixture_expected.json`（保存在夹具目录，另在 `D:\agent-workspace\deliveries\task-L1\` 留档）。因此 Jaccard≥0.8 是**可复现性锁定**，不是独立参考；独立校验来自论文参考 KS 值与已知抑制剂百分位。若 L3/L4 改变样本筛选口径，需要重新生成。
3. **L0 报告中 EGFR 样本覆盖差异**：夹具 EGFR 取前 150 个样本（15 hairpin），论文参考为 19 hairpin，导致 KS −0.528 vs −0.460。属 L0 夹具抽样口径，未在本任务修改。
4. **XSUM 的 median(Σ) ≠ Σ(median)**：当前仍是先按药物取中位数再算 XSUM；实例级方案属 L7b，不在本任务。
5. **药物范围**：仍为全部 `trt_cp`（约 3155 在夹具中），未限制 FDA 批准药；属 L4/L7。
6. `httpx>=0.28` 与 starlette `TestClient` 不兼容的问题按 L0 结论保留 `requirements-dev.txt` 的 `<0.28`，未改回。

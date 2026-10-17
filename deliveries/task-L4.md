# task-L4 · LMNA 药物级随机签名 null → p 值 / FDR

任务ID / 分支 / 基线提交：**L4 / `fix/L4-drug-null` / `origin/main` 3b799ee**
（L1 已合并，基线含 KS 符号修复与 BH 修复）

## 改动文件（文件:行号范围）

| 文件 | 行号 | 内容 |
|---|---|---|
| `backend/config.py` | 62-64 | 新增 `DRUG_NULL_N = int(os.getenv("DRUG_NULL_N", "10000"))` |
| `backend/drug_scorer.py` | 10-17 | 模块说明补充 L4 符号约定 |
| 同上 | 22 | 导入 `DRUG_NULL_N`、`RANDOM_SEED`，复用 `SignatureEngine` 的 BH |
| 同上 | 48-78 | `score_drugs(..., mode="lof")`：新增可选 `mode`（`lof`/`gof`，默认 `lof`） |
| 同上 | 80-206 | 新增 `drug_null(up_idx, down_idx, M=DRUG_NULL_N, batch=500, seed=RANDOM_SEED)` |
| 同上 | 208-275 | `_xsum_score`：为每个药物附加 5 个 null 字段；top/bottom 按 mode + FDR 排序 |
| 同上 | 277-333 | `_wtcs_score`：p/FDR/null_z 字段固定为 `None`（WTCS 不做 null） |
| 同上 | 335-348 | `_drug_records`：top/bottom 输出统一附加新字段 |
| `backend/tests/conftest.py` | 35-36 | 测试期 `DRUG_NULL_N=200`（`setdefault`，可外部覆盖），避免常规用例跑 1 万次 null |
| `backend/tests/test_drug_null.py` | 1-321 | 新增 10 个测试（合成 null、KS、FDR、分批一致性、内存、集成、夹具） |

未改 `main.py` / `task_queue.py` / 前端：top/bottom 记录里自动带上新字段，API 无需改签名。

## 符号约定（重述）

| 量 | 定义 | 方向 |
|---|---|---|
| `mimic` | `Σz(up) − Σz(down)`（`z` 取药物中位数矩阵的行） | **正 = 药物模拟（mimic）查询签名** |
| `score` | `−mimic` | **高分 = 逆转（reversal）**；旧行为不变 |
| `mode="lof"`（默认） | 找逆转药 | top 先按 `fdr_reversal` 升序、再按 `score` 降序；bottom 对称为 `fdr_mimic` 升序、`score` 升序 |
| `mode="gof"` | 找模拟药 | top 先按 `fdr_mimic` 升序、再按 `score` 升序；bottom 对称为 `fdr_reversal` 升序、`score` 降序 |

## 统计口径（p 值 / FDR 方向）

对每个药物，用 `M` 个与查询签名**同样大小**的随机签名（从 G 个基因**无放回**抽
`len(up)+len(down)` 个，前 `len(up)` 个记 +1、其余记 −1）构造经验 null：

```
p_mimic    = (#{null >= obs_mimic} + 1) / (M + 1)   # 单侧（上尾），小 = 药物显著模拟
p_reversal = (#{null <= obs_mimic} + 1) / (M + 1)   # 单侧（下尾），小 = 药物显著逆转
null_z     = (obs_mimic − mean(null)) / sd(null)    # ddof=0；sd=0 时置 0
```

- 两个 p 值互为对称方向，**均为单侧**；本任务没有输出双侧 p（未要求，避免改变语义）。
- `fdr_mimic` 与 `fdr_reversal` 是分别对**全部药物**的对应 p 值做
  Benjamini–Hochberg 校正（复用 L1 修复后的 `SignatureEngine._benjamini_hochberg`，
  与 `scipy.stats.false_discovery_control(method="bh")` 最大差 < 1e-12）。
  两个方向各有一套 FDR，不合并。
- 随机签名按批构造：每批 `(batch, G)` 的权重矩阵 `W` 与 `(batch, n_drug)` 的
  `W @ D`，**不会构造 `(M, n_drug)`**。M=10000、n_drug=20000、batch=500 时，
  单批 null 为 40MB（float32）。
- `p` 的分辨率下限为 `1/(M+1)`。在全局 BH 下，若一个药物集里有大量药物同时落在
  该下限，FDR 可以远小于 `n_drug/(M+1)`；若只有个别药物显著，则可能出现
  “p 很小但 FDR 不显著”的多重校正现象（见下方 🧑‍⚖️）。

## 默认参数

| 参数 | 默认 | 可配置 |
|---|---|---|
| `M` | `DRUG_NULL_N=10000` | 环境变量 `DRUG_NULL_N`；`drug_null(..., M=...)` |
| `batch` | 500 | `drug_null(..., batch=...)` |
| `seed` | `RANDOM_SEED=42` | `drug_null(..., seed=...)` |
| `mode` | `lof` | `score_drugs(..., mode="lof"/"gof")`（HTTP 层暂未暴露，见 🧑‍⚖️） |

## 计算量与实测（本机，CPU BLAS）

合成规模 `G=978, n_drug=20000, M=10000, batch=500`（float32 矩阵常驻内存）：

- 耗时：**1.83 s**（含 978×20000 随机矩阵生成；多次运行 1.7–1.8 s）
- `tracemalloc` 峰值：**170.2 MB**；进程 RSS：**179.9 MB**
- 远低于 1GB 上限；生产用 `mmap_mode='r'` 读矩阵时 Python 堆内存还会更低。

## 测试

新增 `backend/tests/test_drug_null.py`（10 项）：

1. `test_null_distribution_and_p_value_ranges`：null 均值≈0、sd≈√(n_up+n_down)；
   p∈[1/(M+1),1]、FDR∈[0,1] 且 FDR≥p。
2. `test_random_drugs_p_reversal_is_uniform`：随机药 p_reversal / p_mimic 对 U(0,1)
   的 KS 检验 p 均 > 0.01（M=2000；实测 p=0.422 / 0.412）。
3. `test_perfect_reversal_drug_has_small_fdr`：完美逆转药 p_reversal 最小、
   `null_z<-5`、`fdr_reversal<0.01`。
4. `test_fdr_matches_scipy_bh_and_is_monotone`：BH 与 scipy 最大差 <1e-12；FDR 随 p 单调。
5. `test_batched_matches_single_batch`：M=1000，batch=100 vs batch=1000，
   计数/p/FDR 完全一致。
6. `test_empty_and_invalid_signatures`：空签名 → p=1、z=0；越界/非法 M、batch 报错。
7. `test_20k_drugs_peak_memory_under_1gb`：978×20000、M=20，
   `tracemalloc` 峰值 <1GB。
8. `test_xsum_output_fields_and_mode_sorting`：XSUM 每条记录含 5 个新字段；
   lof/gof 的 top 排序方向；WTCS 新字段为 `None`；非法 mode 报错。
9. `test_fixture_known_inhibitor_fdr_mimic_small`（夹具，M=10000）：
   CDK4/EGFR/MTOR 的已知抑制剂 `fdr_mimic<0.05` 且 `p_reversal>0.95`。
10. `test_fixture_fdr_matches_scipy`（夹具）：两方向 FDR 与 scipy BH 一致。

命令（cwd=`backend`）：

```bash
LMNA_FIXTURE_DIR='D:\agent-workspace\deliveries\task-L0\fixtures' \
D:/mine_Anaconda3/python.exe -m pytest -q
```

输出：

```text
........................................s...............                 [100%]
=============================== warnings summary ===============================
tests/test_api_health.py::test_health
  ... PendingDeprecationWarning ...
tests/test_api_health.py::test_health
tests/test_signature_math.py::test_api_status_and_compute_use_min_sh_samples
tests/test_signature_math.py::test_signature_endpoint_returns_new_fields
  ... DeprecationWarning ...
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
55 passed, 1 skipped, 4 warnings in 18.33s
```

（`test_drug_null.py` 单项：`10 passed in 5.91s`。）

## 验收逐条核对

- [x] **合成（G=978、200 随机药 + 1 完美逆转药）完美药 `fdr_reversal<0.01`。**
      用 M=30000 实测 `fdr_reversal=0.0067`、`p_reversal=3.3e-5`。
      注：验收同句写的 M=2000 在 201 个药物下受全局 BH 下限约束
      （最小值约为 `201/2001≈0.1005`），数学上不可能 <0.01；因此 M=2000
      只用于 KS 检验，FDR 阈值用 M=30000 验证（见 🧑‍⚖️ 第 1 条）。
- [x] **随机药 `p_reversal` 对 U(0,1) 的 KS 检验 p>0.01（M=2000）。**
      实测 `p=0.422`（p_mimic 为 0.357）。
- [x] **夹具（M=10000）CDK4/EGFR/MTOR 至少一个已知抑制剂 `fdr_mimic<0.05`。**
      实测最佳值：CDK4 `PHA-793887 fdr=0.000832`；EGFR
      `BIBX-1382 fdr=0.007511`；MTOR `GDC-0980 fdr=0.001186`。
      TOP2A 不要求，实测 ciprofloxacin `fdr=0.008302`。
      （与任务给的参考值 0.0004/0.003/0.003 同量级；差异来自夹具签名/随机种子。）
- [x] **2 万药物规模峰值内存 <1GB。**
      M=10000 实测 170.2 MB（tracemalloc）/ 179.9 MB（RSS）。

## 待人工确认（🧑‍⚖️）

1. **验收的 M=2000 与 `fdr<0.01` 在数学上冲突。**
   201 个药物、M=2000 时，单个完美药的 p 下限是 `1/2001`，全局 BH 至少在
   `201/2001≈0.101`（除非大量药物同时落在 p 下限）。本任务按“实现正确 + 验收
   意图”处理：M=2000 跑 KS，M=30000 验证 FDR<0.01。若希望严格按 M=2000 验收，
   需要把阈值改为 `fdr<0.11` 或把 BH 限定在更小的候选药物集合（后者会改变统计口径，
   未擅自实现）。
2. **生产 M 与检验族大小。** 生产 `n_drug≈2 万`、`M=10000` 时，若显著药物不多，
   全局 BH 的 FDR 可能被多重校正抬高。是否把 `DRUG_NULL_N` 调到 100000 或把 FDR
   限定到 top/bottom 候选集，需要产品/统计口径决策；当前默认严格按任务写 10000。
3. **`mode` 是否要通过 HTTP 暴露。** `score_drugs` 已支持 `lof`/`gof`（默认 lof），
   但 `main.py` 的请求模型和 `task_queue.submit` 未增加参数（遵循“API 只加字段”
   约束）。若 L5 前端需要切换 gof，需要另开小改动。
4. **旧缓存。** 合并后旧的 `cache/drug_scores/*.json` 没有新字段；需按 L2 的缓存
   版本化/清理方案重新生成（L1 上线也已要求删旧 cache）。

## 发现但未处理

- 未输出双侧 p 值（未要求；`p_mimic`/`p_reversal` 是两套单侧检验）。
- WTCS 按任务要求不做药物级 null，5 个字段固定 `None`。
- `all_scores` 的排序仍保持 `score` 降序（未改变旧行为）；只有 `top_drugs` /
  `bottom_drugs` 按 FDR + mode 排序。
- 未在服务器上跑真实 2 万药矩阵（红线：服务器只读；且本机合成规模已满足内存验收）。

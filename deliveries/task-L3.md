# task-L3 · LMNA 基因适用性判档（红/黄/绿）

任务ID / 分支 / 基线提交：`L3` / `fix/L3-suitability` / 开工时 `origin/main` @ `3b799ee`（L1 合并提交）；已 rebase 到最新 main @ `c553da0`（含 L6 工程加固，避免合并冲突）。

## 1. 改动文件

| 文件 | 行号范围 | 改动 |
|---|---|---|
| `backend/suitability.py` | 新增 1–439 | `precheck` / `grade` / `loho_jaccard_min` / `load_annotation`；规则 4.4 修订版 |
| `backend/config.py` | 58–73 | 新增 `GENE_ANNOTATIONS_PATH`（D4，环境变量可配）与判档阈值、`LOHO_MIN_REMAINING` |
| `backend/signature_engine.py` | 18–23, 112–120, 217–290 | 计算前登记 landmark symbol 索引；`compute_signature` 末尾计算 LOHO、敲低效率中位 z、读取注释并写入 `qc` |
| `backend/cache_manager.py` | 42–98 | 药物缓存文件名支持 `mode`：`lof` 保持旧名，`gof` 为 `{GENE}_{method}_gof_drug_scores.json`；`clear_gene` 一并清理 |
| `backend/drug_scorer.py` | 27–115 | `score_drugs(..., mode="lof")`；`gof` 时 top 按 score 升序（模拟药） |
| `backend/main.py` | 49–60, 100–120, 122–170, 187–211, 214–249 | 新增 `/api/genes/{gene}/suitability`；`/compute` hairpin<2→422、`mode`；`/signature` 附 `qc`；`/drugs` 支持 `mode`/`include_red` 与红档屏蔽 |
| `backend/task_queue.py` | 40–120, 157–370 | L6 的 `submit_ex` 增加 `score_mode`（lof/gof）并进入去重键；任务 JSON 同时保留 L6 的 `mode`（fast/full）与 L3 的 `score_mode`；药物缓存按 score_mode；任务结果带 `qc`、红档屏蔽 |
| `backend/tests/test_suitability.py` | 新增 | 红/黄/绿边界、注释、LOHO、夹具四靶点、API 验收 |
| `backend/tests/test_signature_math.py` | 407–413 | 适配 `get_drug_scores(..., mode=)` 的测试替身 |
| `backend/tests/test_task_inline.py` | 14–33 | 适配 worker 的新 `score_mode` 参数 |
| `backend/tests/test_task_hardening.py` | 30–42 | L6 的 worker 测试替身适配 `score_mode` 参数 |

未改动算法本身（KS / BH / 打分方向沿用 L1），未修改范围外代码。

## 2. 符号约定

| 量 | 约定 |
|---|---|
| 样本内秩 | 1 = 表达最高，G = 最低 |
| KS | **KS > 0 = 敲低后该基因上调**（`up_genes`）；KS < 0 = 下调（`down_genes`） |
| LOHO Jaccard | 只使用 **\|KS\|** 排序，与 KS 符号方向无关 |
| k | `k = max(10, len(up_genes) + len(down_genes))`，其中 up/down 是**封顶后**的列表（默认每方向 50） |
| 药物 score | 沿用 L1：`score = −Σz(up) + Σz(down)`；高分 = 逆转 |
| `mode=lof`（默认） | `top_drugs` 按 score **降序**（逆转药），`bottom_drugs` 升序（模拟药） |
| `mode=gof` | `top_drugs` 按 score **升序**（模拟药），`bottom_drugs` 降序（逆转药） |

## 3. LOHO 算法说明

1. 用目标基因全部 shRNA 样本的样本内秩矩阵（`G × n_samples`）。
2. 完整签名：取 `|KS|` 前 `k` 个基因（`k` 见上）。
3. 对每条独立 hairpin（`pert_id` 去重）：
   - 去掉该 hairpin 的**全部样本**；
   - 若剩余样本 < 3，跳过该 hairpin；
   - 用剩余样本重算带符号 KS（与完整签名同一 `ks_uniform_batch`、同一 `G`）；
   - 取 `|KS|` 前 `k` 个基因，与完整签名前 `k` 个求 Jaccard = `|交集| / |并集|`。
4. `loho_jaccard_min` = 所有可用 hairpin 的最小值；一条都算不出则为 `None`（→ 红档）。
5. 细节写入 `qc.reference.loho_k` / `loho_hairpins_used` / `loho_hairpins_skipped`，只展示不判档。

判档（依次判断，规则 4.4 修订版）：

- **红**：独立 hairpin < 2；或算不出签名 / `n_sig < 5`；或 `fast_mode`；或注释判定“不表达 / 组织特异受体或通道”；或不满足黄/绿档。
- **黄**：`n_sig >= 20` 且 `loho_jaccard_min ∈ [0.3, 0.5)`；或满足绿档但注释提示“组织专有”。
- **绿**：`n_sig >= 5` 且 `loho_jaccard_min >= 0.5`。

阈值均可用环境变量覆盖：`SUITABILITY_MIN_HAIRPINS`、`SUITABILITY_MIN_SIG`、`SUITABILITY_YELLOW_MIN_SIG`、`SUITABILITY_JACCARD_GREEN`、`SUITABILITY_JACCARD_RED`、`LOHO_MIN_REMAINING`。

## 4. 测试

新增 `backend/tests/test_suitability.py`（37 个用例，含参数化），覆盖：

- 红/黄/绿边界：`n_sig` 4/5/19/20、`loho` 0.299/0.3/0.499/0.5、`fast_mode`、`data_gate_ok=False`；
- 注释缺失 → `annotation_used=False` 且 reasons 含“未知”，不影响档位；
- 注释各列：不表达→红、组织特异+受体/通道→红、组织专有→绿降黄、广泛表达受体（如 EGFR）不自动判红；
- `load_annotation` 布尔解析、表内无基因、文件不存在；
- LOHO 纯函数：剩余 <3 跳过、重算不变时 Jaccard=1、k 取值；
- 夹具四靶点：precheck、判档、LOHO 参考值、`loho_detail`；
- `ABHD4`（3 样本、1 hairpin）→ `/suitability` `data_gate_ok=False`、`/compute` 422；
- `TOP2A` 红档 → `/drugs` 空列表 + `qc`、`include_red=true` 恢复；
- `mode=gof` 时 CDK4 已知抑制剂进入 top 5%；
- 任务结果红档屏蔽。

`cd backend && LMNA_FIXTURE_DIR=D:\agent-workspace\deliveries\task-L0\fixtures python -m pytest -q`：

```
.....................................s.................................. [ 67%]
..................................                                       [100%]
105 passed, 1 skipped, 6 warnings in 14.34s
```

无夹具回归（`python -m pytest -q`）：

```
sssssssssss.........ssssssssssssssssss....s..........ss................. [ 67%]
.....sssssssssssssss..............                                       [100%]
59 passed, 47 skipped in 4.40s
```

完整日志：`D:\agent-workspace\deliveries\task-L3\pytest_with_fixture.log`、`pytest_without_fixture.log`（不入 git）。

## 5. 验收逐条核对

夹具参数：`BOOTSTRAP_N=200`（conftest）、`FDR_THRESHOLD=0.05`、`KS_THRESHOLD=0.2`、`FAST_MODE_TOP_N=0`、`MAX_GENES_PER_DIRECTION=50`。

| 验收项 | 结果 |
|---|---|
| CDK4 → green | [x] `n_sig=228`，`LOHO=0.5873`（参考 0.587，Δ=0.000） |
| EGFR → green | [x] `n_sig=37`，`LOHO=0.6087`（参考 0.532，Δ=0.077，见 §7.1） |
| MTOR → green | [x] `n_sig=82`，`LOHO=0.5248`（参考 0.549，Δ=0.024） |
| TOP2A → red | [x] `n_sig=85`，`LOHO=0.2593`（参考 0.290，Δ=0.031，<0.3 判红） |
| 1 个 hairpin 基因 | [x] `ABHD4`：3 样本、1 hairpin；`/suitability` `data_gate_ok=false`；`/compute` 422，detail 含“hairpin / 脱靶” |
| 红档 `/drugs` | [x] `TOP2A`：`top_drugs=[]`、`bottom_drugs=[]`、`qc.grade=red`、`red_suppressed=true`；`include_red=true` 返回非空 |
| `mode=gof` 抑制剂 top 5% | [x] `palbociclib` 升序第 39/3155（1.24%）、`alvocidib` 4.75%、`ryuvidine` 4.06% |

## 6. 新字段清单（L5 依赖，务必按此对接）

### 6.1 `GET /api/genes/{gene}/suitability`（新增）

```json
{
  "gene_name": "CDK4",
  "cached_signature": true,
  "grade": "green",
  "precheck": {
    "gene_name": "CDK4",
    "n_samples": 86,
    "n_hairpins": 7,
    "n_cells": 11,
    "cell_lines": ["A375", "..."],
    "data_gate_ok": true,
    "reasons": ["数据前置门槛通过：..."]
  },
  "qc": {
    "grade": "green",
    "reasons": ["..."],
    "loho_jaccard_min": 0.5873,
    "n_sig": 228,
    "reference": {
      "n_cells": 11,
      "cell_lines": ["..."],
      "n_hairpins": 7,
      "n_samples": 86,
      "target_is_landmark": true,
      "target_ks": -0.7457,
      "target_median_z": -3.45,
      "loho_k": 100,
      "loho_hairpins_used": 7,
      "loho_hairpins_skipped": 0
    },
    "annotation_used": false,
    "rule_version": "4.4-rev"
  }
}
```

`qc`/`grade` 在无缓存签名时为 `null`；`precheck` 永远返回（无样本时 `n_samples=0`、`data_gate_ok=false`，HTTP 仍为 200）。

### 6.2 其它接口（只加字段，未改名）

- `GET /api/genes/{gene}/signature` 新增：`qc`、`n_hairpins`、`n_cells`。
- `GET /api/genes/{gene}/drugs` 新增查询参数：`mode=lof|gof`、`include_red=true|false`；响应新增：`mode`、`qc`、`include_red`、`red_suppressed`（原 `gene_name/method/n_up_genes/n_down_genes/top_drugs/bottom_drugs` 不变）。
- `POST /api/genes/{gene}/compute` 请求新增 `mode`，响应新增 `mode`；`method` 不变；L6 的 `deduplicated` 字段保留。任务 JSON 中 `mode` 仍是 L6 的 fast/full，L3 的 lof/gof 存在 `score_mode`（两者都进去重键）。
- `GET /api/tasks/{id}` 结果：
  - `result.signature` 新增 `qc`、`n_hairpins`、`n_cells`；
  - `result.drug_results` 新增 `mode`、`qc`、`red_suppressed`；红档时 `top_drugs`/`bottom_drugs` 为空。
- 签名缓存 JSON 新增：`qc`、`n_hairpins`、`n_cells`、`loho_jaccard_min`、`loho_detail`、`target_median_z`。
- 药物缓存文件名：`{GENE}_{method}_drug_scores.json`（lof，兼容旧名）、`{GENE}_{method}_gof_drug_scores.json`（gof）。

## 7. 待人工确认（🧑‍⚖️）

### D4：第一层外部注释（仍未决）

当前实现严格按“存在就读、不存在显示未知”：

- 路径：`GENE_ANNOTATIONS_PATH`，默认 `DATA_DIR/gene_annotations.tsv`；
- 列：`gene, expressed_in_l1000_cells, tissue_specific, receptor_or_channel`（布尔写法支持 true/false、1/0、yes/no、是/否，空值为未知）；
- 文件不存在 / 无该基因 / 缺列 / 读取失败：`annotation_used=false`，reasons 里写“第一层显示为‘未知’，请研究者自行判断”，**不改变档位**；
- **Repurposing Hub moa 文本未下载、未提交进仓库**。原分析用的 2020-03 版随 calibration 缺失；该数据仅限非商业用途、许可需确认。请用户确认：
  1. 是否上线 `gene_annotations.tsv`，以及由谁生成、放在哪个路径；
  2. `receptor_or_channel` 是否按 Repurposing Hub moa 派生（若需要下载，走 7897 代理，仅用于生成注释，不提交原始大文件）；
  3. 注释表的许可与版本如何记录。

## 8. 发现但未处理

1. **EGFR LOHO 偏差**：夹具 `LOHO=0.609` vs 报告参考 `0.532`（Δ=0.077）。夹具 EGFR 只取前 150 个 `trt_sh`（15 个 hairpin），论文参考集为 19 个 hairpin；L1 已记录同一覆盖差异（KS −0.528 vs −0.460）。档位仍为绿档；参考实现与 2020-03 校准数据均不在本地，无法“重跑参考实现”进一步对齐。测试容差暂设 ±0.10 并在用例注释中说明；其余三靶点在 ±0.05 内。
2. **`gof` 药物缓存需先按 `mode=gof` 计算**：`/drugs` 只读缓存，不会即席重算；前端需在计算任务里带 `mode`。L2 未实现，缓存版本化/失效策略未纳入本任务，本次只把 `mode` 放进文件名。
3. **旧签名缓存没有 `qc`**：上线后需重算签名（或至少删 `cache/signatures`）才能获得判档；在重算前 `/signature`、`/drugs` 的 `qc` 为 `null`，红档屏蔽不会生效。
4. **`target_median_z` 口径**：直接取 Level5 矩阵靶基因行的中位值（Level5 为 z-score）；靶基因不是 landmark 时为 `null`（实测 MTOR 不是 landmark）。若后续换用非 Level5 数据，该字段含义需重新定义。
5. **生产 L5 路径仍受 L8 列序问题影响**：本任务全部验收走 `FixtureProvider`；L1 已报告 `col_sig_ids.csv` 与 `fast_matrix.npy` 列序不一致，生产签名正确性依赖 L8（PROGRESS 中 L8 进行中）。
6. **任务结果无 `include_red`**：按任务原文只在 `/drugs` 提供 `include_red`；任务结果对红档一律屏蔽药物列表，科研排查请用 `/drugs?include_red=true`。
7. **注释表无自动派生**：本任务未实现从 Repurposing Hub moa 自动生成 `receptor_or_channel`，避免引入许可不明数据；待 D4 决定后再做。

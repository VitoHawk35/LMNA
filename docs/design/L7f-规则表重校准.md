# L7f 阶段1：判档规则表 L3 口径重校准报告（空隙区修复）

- 任务：L7f 阶段1（面板重跑 + 重校准报告）｜ 分支：`fix/L7f-grading-recal`
- 基线：main @ fa836b2（L7e 已合并，RULE_VERSION 4.5）
- 红线遵守：服务器只读（写入仅 `/home/keji/l3_tmp/`）、未安装依赖、
  未重启/修改任何运行中服务、大文件未入库、只推分支不合并。

## 0. TL;DR

- **推荐方案 A：黄档 n_sig 下限 20 → 5**（与绿档一致），即空隙区
  [5,20)×[0.3,0.5) 整体并入黄档；绿档、红档线、注释层、D1 防线全部不动。
- 面板 21 靶点 × L3/L5 两侧全量重跑（L3 12.4 CPU·h / 11 分片，
  L5 4.1 CPU·h / 7 分片，56 核服务器约 2.5h 墙钟）。
- 关键证据：L3 空隙区 6 靶点（EGFR 0.690、HDAC1 0.890、ALK 0.788、
  FGFR1 0.595、CDK2 0.370、PIK3CA 0.310），**空隙内 LOHO 与 AUROC 不单调
  （LOHO=0.333 簇反而是 AUROC 最高的一簇）**——任何"空隙内再加 LOHO 门槛"
  的 B/C 类方案都会选错对象（B35/B40 只救回 AUROC 最差的 CDK2/PIK3CA，
  却把 AUROC 0.89 的 HDAC1 留在红档）。
- 一致性指标：L3 侧 Spearman(档位, AUROC) 方案 A = 0.379 > 现规则 0.337；
  L5 侧方案 A = 0.349（现规则 0.390），差异由 MET-L5 单点（AUROC 0.36）
  贡献。所有方案单调性网格断言 0 违规、两侧均无降档、阴性对照两侧通过。
- **超范围但重要的发现**：TP53/MYC 在 L3 口径下按 4.5 现状本就不红
  （TP53 绿、MYC 绿、LMNA 黄）——稳定性规则无法识别"不可成药"，
  这是注释层（D4）的职责，与本次方案无关，需用户知悉（§10-3）。

## 1. 问题复述

`backend/suitability.py` `grade()`（RULE_VERSION 4.5）核心规则：

| 档 | 核心条件 |
|---|---|
| 绿 | n_sig ≥ 5 且 LOHO ≥ 0.5 |
| 黄 | n_sig ≥ 20 且 0.3 ≤ LOHO < 0.5 |
| **空隙** | n_sig ∈ [5,20) 且 LOHO ∈ [0.3,0.5) → else → **红** |

L7e 把签名侧切到 L3（实例级 robust z）后 n_sig 分布双向移动且 LOHO 整体上升
（L7e 阶段2 §7），实测 EGFR-L3（n_sig=18，LOHO=0.385，AUROC=0.690）落入空隙
被拒答，而同靶点 L5 口径为黄档（n_sig=25，LOHO=0.316）。本任务用 21 靶点
面板在 L3/L5 两侧重校准，而不是只对 EGFR 打补丁。

## 2. 面板（21 靶点 = 基准 10 + LMNA + 扩展 10）

定义：`scripts/l7f_panel/panel_def.py`（含每靶点金标准药物别名组、出处、
预期档位）。金标准整理口径沿用 `round2/verification/多基因测试-权威基准.md`
（Drug Repurposing Hub MoA / 药品说明书靶点 / 文献共识）；别名单个组内任一
变体命中 `pert_iname`（小写精确匹配）即算在场，与 `scripts/l3_exp1_accuracy.py`
GOLD 口径一致。

覆盖面设计：预期绿（CDK4/CDK6/MTOR/PIK3CA/HDAC1/AURKA/PLK1/MAP2K1）、
预期黄（AKT1/BRAF/JAK2/CDK9）、预期空隙（EGFR/ERBB2/ALK/MET/FGFR1/CDK2——
RTK 与部分 CDK 在 LINCS KD 中签名偏弱）、难度/阴性对照仍红
（TP53/MYC/LMNA，无直接抑制剂）。

### 2.1 数据覆盖核实（服务器实测，`coverage_l3.json` / `coverage_l5.json`）

- **21/21 靶点两侧均有 shRNA 数据**（`list_available_genes` 命中），hairpin 数
  全部 ≥ 2（最低 LMNA 3、MAP2K1 5），数据前置门槛全过。
- L3 侧样本/hairpin：MET 826/17、MYC 860/16、BRAF 689/14、EGFR 680/20、
  AKT1 615/12、CDK2 614/16、CDK6 542/16、MTOR 455/18、AURKA 417/9、
  HDAC1 367/12、ERBB2 313/9、PIK3CA 286/11、CDK4 210/11、MAP2K1 196/5、
  TP53 196/7、JAK2 144/11、PLK1 131/11、FGFR1 129/12、CDK9 113/10、
  ALK 111/9、LMNA 93/3（合计 7,987 实例）。
- L5 侧同靶点样本约为 L3 的 1/3（MODZ 聚合，合计 2,761；如 EGFR 240/20、
  CDK4 71/11），与 L7e 阶段2 观测一致。
- **金标准药物在场**（LINCS 19,811 药，别名组精确匹配）：18 个有金标准的
  靶点每组至少 1 药在场。较弱者：CDK6 1/3（仅 palbociclib；ribociclib/
  abemaciclib 不在 LINCS）、ALK 2/5（crizotinib、nvp-tae684）、CDK2 2/4
  （roscovitine、alvocidib）、PLK1 2/4（bi-2536、on-01910）、AKT1 2/5
  （mk-2206、triciribine）。缺席者均为 LINCS 未收录的新药
  （与 L7e 阶段2 §6.1 锚点核对一致）。CDK6 AUROC 仅 1 个正例，
  解释时谨慎（详见 §10）。

## 3. 方法口径

- 签名侧：L3 派生层 `/home/keji/l3_tmp/derived/l3_v1/`（474,096×978，
  L7e 交付，manifest 校验齐全）与 L5 MODZ（默认）两侧各跑一遍；
  药物侧两侧同为 L5 MODZ 中位数矩阵（19,811 药）。
- 参数与生产一致：KS≥0.2、FDR<0.001、BOOTSTRAP_N=100,000、每方向封顶 50、
  DRUG_NULL_N=10,000、seed 42（`config.signature_params()` 入 JSON 可查，
  分片 JSON 的 `params`/`grading_thresholds` 字段逐分片留档）。
- 驱动：`scripts/l7f_panel/run_panel.py`（分片并行；签名落盘缓存带参数哈希，
  换参数/换源自动隔离；复用 L7e exp1 口径：真实后端
  provider_factory → SignatureEngine → DrugScorer，AUROC 用 mimic 分方向）。
- 四元组：n_sig（封顶前 FDR+KS 通过数）、LOHO（留一 hairpin Jaccard 最小值）、
  AUROC（自身金标准抑制剂，mimic 方向）、判档（RULE_VERSION 4.5 实测输出）。
- 与 L7e 阶段2 的口径一致性：CDK4/EGFR/MTOR/BRAF 四靶点两侧交叉核对
  （`crosscheck_stage2.py`，见 §4.1）。
- 阴性对照：20 个随机签名（50 up + 50 down，seed 42，null M=10,000）：
  (a) fdr_reversal<0.05 药物比例 <1%（exp1 口径）；
  (b) 走真实 `grade()` 判档必须全红（随机签名无 hairpin → LOHO=None → 红）。
- 运行开销：L3 侧 CPU 合计 44,553 s（11 分片并行，含秩矩阵缓存构建），
  L5 侧 14,740 s（7 分片）；56 核服务器墙钟约 2.5h（2026-11-03 16:39 启动，
  当日 19:0x 全部完成）。

## 4. 四元组总表

判档列为 RULE_VERSION 4.5 实测输出；**加粗** = 落入空隙区
（n_sig∈[5,20) 且 LOHO∈[0.3,0.5)）；AUROC "—" = 无金标准（难度对照）；
AUROC=0.500 者多为 n_sig=0 空签名（打分全零）。

| 靶点 | 角色/预期 | L3 n_sig | L3 LOHO | L3 AUROC | L3 档(4.5) | L5 n_sig | L5 LOHO | L5 AUROC | L5 档(4.5) |
|---|---|---|---|---|---|---|---|---|---|
| AKT1 | base/黄 | 43 | 0.564 | 0.783 | 绿 | 78 | 0.451 | 0.745 | 黄 |
| ALK | ext/空隙 | **10** | **0.333** | **0.788** | **红(空隙)** | 0 | 0.176 | 0.500 | 红 |
| AURKA | ext/绿 | 53 | 0.656 | 0.822 | 绿 | 65 | 0.529 | 0.820 | 绿 |
| BRAF | base/黄 | 24 | 0.655 | 0.688 | 绿 | 25 | 0.562 | 0.743 | 绿 |
| CDK2 | ext/空隙 | **6** | **0.429** | **0.370** | **红(空隙)** | 26 | 0.444 | 0.398 | 黄 |
| CDK4 | base/绿 | 101 | 0.676 | 0.819 | 绿 | 83 | 0.636 | 0.815 | 绿 |
| CDK6 | ext/绿 | 25 | 0.724 | 0.990 | 绿 | 0 | 0.667 | 0.500 | 红 |
| CDK9 | ext/黄 | 35 | 0.400 | 0.508 | 黄 | 0 | 0.333 | 0.500 | 红 |
| EGFR | base/空隙 | **18** | **0.385** | **0.690** | **红(空隙)** | 25 | 0.316 | 0.728 | 黄 |
| ERBB2 | ext/空隙 | 28 | 0.302 | 0.289 | 黄 | 62 | 0.333 | 0.379 | 黄 |
| FGFR1 | ext/空隙 | **16** | **0.333** | **0.595** | **红(空隙)** | 0 | 0.176 | 0.500 | 红 |
| HDAC1 | base/绿 | **10** | **0.333** | **0.890** | **红(空隙)** | 34 | 0.360 | 0.776 | 黄 |
| JAK2 | base/黄 | 26 | 0.444 | 0.586 | 黄 | 0 | 0.250 | 0.500 | 红 |
| LMNA | proj/红 | 51 | 0.397 | — | 黄 | 0 | 0.111 | — | 红 |
| MAP2K1 | ext/绿 | 29 | 0.208 | 0.991 | 红 | 27 | 0.256 | 0.973 | 红 |
| MET | ext/空隙 | 1 | 0.538 | 0.558 | 红 | **5** | **0.429** | **0.360** | **红(空隙)** |
| MTOR | base/绿 | 31 | 0.590 | 0.956 | 绿 | 40 | 0.404 | 0.997 | 黄 |
| MYC | base/红 | 58 | 0.785 | — | 绿 | 90 | 0.459 | — | 黄 |
| PIK3CA | base/绿 | **9** | **0.429** | **0.310** | **红(空隙)** | 0 | 0.538 | 0.500 | 红 |
| PLK1 | ext/绿 | 38 | 0.520 | 0.863 | 绿 | **16** | **0.455** | **0.799** | **红(空隙)** |
| TP53 | base/红 | 79 | 0.510 | — | 绿 | 40 | 0.333 | — | 黄 |

散点图（n_sig × LOHO，AUROC 着色，L3/L5 双联）：
`scripts/l7f_panel/local_results/scatter_nsif_loho.png`
（由 `scripts/l7f_panel/plot_scatter.py` 生成，可复跑）；
三元组原始数据在同目录 `analysis.json`（`sides.*.tuples`）。

### 4.1 与 L7e 阶段2 四靶点交叉核对（`crosscheck_stage2.py` 服务器实测）

| 靶点 | L3 | L5 |
|---|---|---|
| CDK4 | **MATCH**（101/0.6762/0.8187/绿 逐项一致） | **MATCH**（83/0.6364/0.8155/绿） |
| EGFR | **MATCH**（18/0.3846/0.6904/红） | **MATCH**（25/0.3158/0.7284/黄） |
| MTOR | **MATCH**（31/0.5897/0.9564/绿） | 签名指标逐项一致（40/0.4035/黄），AUROC 0.9968→0.9972（Δ=4e-4） |
| BRAF | **MATCH**（24/0.6552/0.6878/绿） | **MATCH**（25/0.5625/0.7428/绿） |

MTOR-L5 的 4e-4 AUROC 尾差原因：签名侧逐位一致（n_sig/LOHO/档位全同），
差异在药物侧——L7e 阶段2 用的是合并前 follow-up 修复之前的 backend 副本
构建的药物中位数缓存，本次在全新缓存目录（l7f_cache_l5）用合并后 backend
重建，极少数中游名次的药物位置移动；对判档与结论无影响。

### 4.2 分布分析

- **空隙区两侧共 8 个靶点-侧**：L3 侧 6 个（EGFR、HDAC1、ALK、FGFR1、
  CDK2、PIK3CA），L5 侧 2 个（MET、PLK1）。占 L3 面板的 29%——L3 口径下
  n_sig 落 [5,20) 的靶点确实增多（L7e §7 预测兑现）。
- **空隙区 AUROC 双峰且与 LOHO 不单调**（本报告最核心的分布事实）：
  - 高 AUROC 簇：HDAC1 0.890、ALK 0.788、PLK1(L5) 0.799、EGFR 0.690、
    FGFR1 0.595——其中 L3 的 LOHO 全是 **0.333**（空隙区下沿）；
  - 低 AUROC 簇：CDK2 0.370、MET(L5) 0.360、PIK3CA 0.310——LOHO 反而在
    **0.429**（空隙区上沿）。
  - 即在 [0.3,0.5) 内用 LOHO 再切一刀，会把"该救的"切成"不该救的"。
- n_sig=0 靶点（L5 侧 6 个：ALK/CDK6/CDK9/FGFR1/JAK2/PIK3CA）按红线判红，
  AUROC 退化为 0.500（空签名打分全零），行为正确。
- **LOHO<0.3 红线咬到高 AUROC 靶点**：MAP2K1 两侧 AUROC 0.991/0.973，
  但仅 5 条 hairpin，LOHO 0.208/0.256 → 红。属红线下缘议题，不在本任务
  修复范围，记录于 §10-4。
- 难度对照：TP53/MYC/LMNA 在 L3 下分别为绿/绿/黄、L5 下黄/黄/红——
  **4.5 现状下它们就不是全红**（§10-3 详述）。

## 5. 候选方案与对比矩阵

候选（均只放宽黄档、从不收紧，结构上无降档；另附逐格单调性断言）：

| 方案 | 黄档核心条件（绿档不变：n_sig≥5 且 LOHO≥0.5） |
|---|---|
| current（4.5） | n_sig≥20 且 0.3≤LOHO<0.5 |
| A | n_sig≥5 且 0.3≤LOHO<0.5（空隙整体并入黄档） |
| B35 / B40 / B45 | n_sig≥20 时同 4.5；n_sig∈[5,20) 时要求 LOHO≥θ（θ=0.35/0.40/0.45） |
| C | 连续斜坡：LOHO ≥ max(0.3, 0.55−0.02×n_sig)（n_sig=5→0.45，10→0.35，≥13→0.3） |

单调性定义：固定 LOHO 时 n_sig 增大不得降档；固定 n_sig 时 LOHO 增大不得
降档。`analyze_results.py::check_monotonicity` 在 n_sig∈[0,60] ×
LOHO∈[0.30,1.00]（步长 0.005）网格逐格断言——**6 个方案全部 0 违规**。

对比矩阵（分布 = 红/黄/绿计数；sp = Spearman(档位, AUROC)，仅统计有金标准
的 18 靶点；救回 = 相对 4.5 由红升黄的空隙区靶点）：

| 方案 | L3 红/黄/绿 | L3 sp | L5 红/黄/绿 | L5 sp | L3 救回（AUROC） | L5 救回（AUROC） |
|---|---|---|---|---|---|---|
| current | 8/4/9 | 0.337 | 10/8/3 | 0.390 | — | — |
| **A** | **2/10/9** | **0.379** | 8/10/3 | 0.349 | EGFR .69、HDAC1 .89、ALK .79、FGFR1 .60、CDK2 .37、PIK3CA .31 | PLK1 .80、MET .36 |
| B35 | 5/7/9 | 0.233 | 8/10/3 | 0.349 | EGFR .69、CDK2 .37、PIK3CA .31 | PLK1 .80、MET .36 |
| B40 | 6/6/9 | 0.213 | 8/10/3 | 0.349 | CDK2 .37、PIK3CA .31 | PLK1 .80、MET .36 |
| B45 | 8/4/9 | 0.337 | 9/9/3 | 0.478 | 无 | PLK1 .80 |
| C | 5/7/9 | 0.281 | 9/9/3 | 0.478 | EGFR .69、FGFR1 .60、PIK3CA .31 | PLK1 .80 |

各方案安全性（验收要求逐条）：

- **单调性**：6 方案网格断言全部通过（见上）。
- **TP53/MYC 仍红**：⚠️ 在 L3 口径下 **4.5 现状就不成立**（TP53 绿、MYC 绿、
  LMNA 黄）——所有候选方案与 4.5 在这三个靶点上判档完全一致（它们都不在
  空隙区），即方案对比对该条无区分度；根本原因是稳定性规则不编码
  "可成药性"，属注释层职责，见 §10-3，提请用户决策。
- **20 随机签名仍全红**：✓（§6）。
- **判档↔AUROC 一致性不劣于现规则**：L3 侧 A 最优（0.379 > 0.337）；
  L5 侧 A 略降（0.349 < 0.390），全部由 MET-L5 单点（AUROC 0.36，n_sig=5
  踩线）贡献；B45/C 在 L5 最高（0.478）但在 L3 更低（0.337/0.281）且
  救不回 EGFR/HDAC1/ALK 等主要目标。
- **L5 口径不回退**：所有方案在任何一侧均无降档
  （`analysis.json::no_downgrade_check` 全空）——候选都只放宽空隙区。

## 6. 阴性对照

| 侧 | 药物 FDR<0.05 比例 max | mean | <1% 判定 | 20 随机签名判档 |
|---|---|---|---|---|
| L3 | 0.0000% | 0.0000% | ✅ | **全红** ✅ |
| L5 | 0.0000% | 0.0000% | ✅ | **全红** ✅ |

结构性论证：随机签名无 hairpin 结构 → LOHO=None → 在任何候选方案下都
命中"无法计算 LOHO → 红"（所有候选只改 0.3≤LOHO<0.5 带内的 n_sig 条件，
不动 LOHO=None 防线、不动 n_sig<5 红线、不动 LOHO<0.3 红线）。

## 7. 推荐方案与理由

**推荐方案 A：黄档核心条件改为 `n_sig ≥ 5 且 0.3 ≤ LOHO < 0.5`**
（实现即 `SUITABILITY_YELLOW_MIN_SIG` 20→5，绿/红线与注释层、D1 防线不动，
RULE_VERSION 4.5→4.6）。

理由（全部有 §4/§5 数据支撑）：

1. **空隙内 LOHO 无区分度**（§4.2）：本面板 L3 空隙 6 靶点中 AUROC 最高的
   三个（HDAC1 0.890、ALK 0.788、EGFR 0.690…加上 FGFR1 0.595）LOHO 全部
   挤在 0.333，而 AUROC 最差的两个（CDK2 0.370、PIK3CA 0.310）LOHO 反而
   0.429。B 类方案（θ=0.35/0.40）救回的恰是最差的一簇、把 HDAC1/ALK 留在
   红档，L3 一致性指标随 θ 升高单调恶化（sp 0.233/0.213 < 现规则 0.337）。
   C（斜坡）比 B 好但仍漏掉 ALK/HDAC1（n=10 时门槛 0.35 > 0.333）。
2. **A 在 L3 侧一致性最优**：sp 0.379，高于现规则与所有 B/C；黄档均值
   从 0.461 升到 0.559（把高 AUROC 空隙靶点移入黄档），绿档 0.846 不变。
3. **黄档语义是弱背书**：黄档本就"照常给出药物列表，但建议再补一种证据"。
   把 CDK2/PIK3CA（AUROC 0.3x）放进黄档的代价是用户看到一个带警示的列表
   （且其 fdr_reversal<0.05 药物数会如实显示在摘要里）；把 HDAC1/ALK/EGFR
   （AUROC 0.7-0.9）留在红档的代价是**硬拒答且不给列表**——两类错误严重度
   不对称，A 选对了方向。
4. **简单与可维护**：只动一个数字，消除绿 n_sig≥5 / 黄 n_sig≥20 的 L5 时代
   不对称；单调性由构造保证；测试面最小。
5. **两口径安全**：L5 侧仅 2 靶点受影响（PLK1 升黄是改进；MET 升黄是唯一
   代价，AUROC 0.36 但 n_sig=5 本就踩红线边缘），无任何降档；支持一套规则
   两口径共用（D-d）。

## 8. 决策点答复建议（D-a ~ D-d）

- **D-a 推荐方案与切点**：方案 A，即黄档 `n_sig ≥ 5 且 LOHO ∈ [0.3, 0.5)`；
  不引入新切点（LOHO 0.3/0.5 维持，L7e 阶段2 已论证）。
- **D-b 黄档 n_sig 阈值**：20 → **5**（与绿档下限对齐；20 是 L5 时代经验值，
  L3 口径下 n_sig 分布整体上移/空隙占比 29%，继续保留会把近三成面板靶点
  推入无指引的红档）。
- **D-c 空隙区理由文案措辞**（面向研究者的指引）：
  - 升黄者（原空隙区）：
    「签名稳定性中等（LOHO Jaccard=X.XX ∈ [0.3, 0.5)）且显著基因数偏少
    （n_sig=N）：药物列表照常给出，但命中信心低于典型黄档；建议优先选
    排名靠前且机制明确的候选，并补一种正交证据（如第二种细胞系或
    CRISPR 复敲）再做湿实验。」
  - 方案 A 下不存在"空隙残留仍红"文案需求（空隙整体并入黄档）；若最终
    采纳 B/C 类方案再补残留文案。
  - 废弃 4.5 的「未满足绿档或黄档条件」（无指导性）。
- **D-d L5 口径**：一套规则两口径共用，不为 L5 单独设阈值。依据：候选
  方案在 L5 侧零降档、仅 2 靶点受影响；分口径设阈值会让测试面翻倍而
  收益只有一个边界靶点（MET-L5）。

## 9. 复跑与抽查入口

```bash
# 服务器产物：/home/keji/l3_tmp/l7f_results/
#   coverage_l3.json coverage_l5.json
#   panel_l3_shard0..10.json panel_l5_shard0..6.json（+ 同名 .log）
#   signatures_l3/ signatures_l5/（签名落盘缓存，文件名含参数哈希）
#   crosscheck_stage2.py（与 L7e 阶段2 交叉核对）
# 本地副本与合并分析：scripts/l7f_panel/local_results/（已随分支提交）

# 覆盖核查（分钟级）
ssh -i ~/.ssh/lmna_deploy keji@10.39.15.238
cd /home/keji/l3_tmp/l7f   # 本分支代码部署点（backend/ + scripts/l7f_panel/）
PY=~/miniconda3/envs/cmap/bin/python
DATA_PROVIDER=l3 L3_DERIVED_DIR=/home/keji/l3_tmp/derived/l3_v1 \
CMAP_DATA_DIR=/home/keji/cmap_v2_data LMNA_CACHE_DIR=/home/keji/l3_tmp/l7f_cache \
LINCS_INTEGRITY_MODE=off \
$PY -B scripts/l7f_panel/check_coverage.py --side l3 \
  --out /home/keji/l3_tmp/l7f_results/coverage_l3.json

# 面板重跑（本任务实际跑法：L3 侧 11 分片、L5 侧 7 分片并行，56 核服务器）
for i in $(seq 0 10); do
  DATA_PROVIDER=l3 L3_DERIVED_DIR=/home/keji/l3_tmp/derived/l3_v1 \
  CMAP_DATA_DIR=/home/keji/cmap_v2_data LMNA_CACHE_DIR=/home/keji/l3_tmp/l7f_cache \
  BOOTSTRAP_N=100000 FDR_THRESHOLD=0.001 KS_THRESHOLD=0.2 DRUG_NULL_N=10000 \
  LINCS_INTEGRITY_MODE=off FAST_MODE_TOP_N=0 \
  nohup $PY -B -u scripts/l7f_panel/run_panel.py --side l3 --shard $i/11 \
    $( [ $i -eq 0 ] && echo --with-neg-ctrl ) \
    --out /home/keji/l3_tmp/l7f_results/panel_l3_shard$i.json \
    > /home/keji/l3_tmp/l7f_results/panel_l3_shard$i.log 2>&1 &
done
# L5 侧：DATA_PROVIDER=l5、LMNA_CACHE_DIR=/home/keji/l3_tmp/l7f_cache_l5、
#        --shard $i/7、输出 panel_l5_shard$i.json

# 本地分析（合并分片 → 方案对比）
PYTHONIOENCODING=utf-8 D:/mine_Anaconda3/python.exe -I \
  scripts/l7f_panel/analyze_results.py \
  --l3 scripts/l7f_panel/local_results --l5 scripts/l7f_panel/local_results \
  --out scripts/l7f_panel/local_results/analysis.json
```

抽查建议（主agent）：任取一个分片 JSON（如 panel_l3_shard0.json）核对
`params` 与 `grading_thresholds` 字段；任取一靶点（如 EGFR）用同一环境
重跑 `run_panel.py --side l3 --targets EGFR --out /tmp/egfr.json`
（签名命中缓存秒出，结果应逐字节一致）。

## 10. 已知边界与风险

1. **面板规模**：21 靶点、L3 空隙区 6 个——样本量小。方案 A 不依赖切点
   选择，对该不确定性最稳健；B/C 的切点在小样本上不可靠（§4.2 已演示
   切点选错对象的机制）。
2. **HDACi 非特异性**：HDAC1 AUROC 0.890 可能部分来自 HDAC 抑制剂在
   连通性图谱中的普遍高分（权威基准文档已警示）；判读空隙区 AUROC 时
   已考虑，不影响"救回"方向性结论。
3. **TP53/MYC/LMNA 在 L3 下不红**（重要，超范围）：稳定性规则（n_sig/LOHO）
   度量的是"签名可复现性"，不编码"靶点可成药性"——TP53 (79, 0.510) 绿、
   MYC (58, 0.785) 绿、LMNA (51, 0.397) 黄。这在 4.5 现状即如此，与候选
   方案无关（各方案判这三者完全一致）。任务卡验收"TP53/MYC 仍红"在 L3
   口径下事实上不可达（除非引入新规则维度）；建议由第一层注释（D4 的
   gene_annotations.tsv，当前未部署）承载"无直接抑制剂"语义，或由用户
   拍板是否接受"稳定但不可成药 → 给列表"的行为。提请阶段2 前决策。
4. **红线下缘反例**：MAP2K1 两侧 AUROC 0.99/0.97 却因 LOHO<0.3（仅 5 条
   hairpin）判红。这是 0.3 红线的保守性代价，与空隙区无关，本任务不动；
   若未来要放宽红线，需要同等规模面板单独论证。
5. **AUROC 方向性**：CDK2/PIK3CA/ERBB2 的 mimic 向 AUROC < 0.5，说明其
   金标准抑制剂落在打分列表的逆转端（药理方向与 KD 签名相反），属已知
   的通路层面现象（BRAF/MEK 类似，L7e §6.2 讨论过）；本报告 AUROC 一律
   沿用 mimic 方向口径。
6. **CDK6 AUROC 仅 1 个正例**（palbociclib）：统计意义弱，仅作参考。
7. L3 侧 250 个基因全局剔除（L7e 已知代价，含 HIF1A/DNMT1 等）继续生效，
   所有 L3 签名一致缺这些基因。

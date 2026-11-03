# L7f 阶段1：判档规则表 L3 口径重校准报告（空隙区修复）

- 任务：L7f 阶段1（面板重跑 + 重校准报告）｜ 分支：`fix/L7f-grading-recal`
- 基线：main @ fa836b2（L7e 已合并，RULE_VERSION 4.5）
- 红线遵守：服务器只读（写入仅 `/home/keji/l3_tmp/`）、未安装依赖、
  未重启/修改任何运行中服务、大文件未入库、只推分支不合并。

## 0. TL;DR

（待数据填：推荐方案、切点、关键数字）

## 1. 问题复述

`backend/suitability.py` `grade()`（RULE_VERSION 4.5）核心规则：

| 档 | 核心条件 |
|---|---|
| 绿 | n_sig ≥ 5 且 LOHO ≥ 0.5 |
| 黄 | n_sig ≥ 20 且 0.3 ≤ LOHO < 0.5 |
| **空隙** | n_sig ∈ [5,20) 且 LOHO ∈ [0.3,0.5) → else → **红** |

L7e 把签名侧切到 L3（实例级 robust z）后 n_sig 分布双向移动且 LOHO 整体上升
（L7e 阶段2 §7），实测 EGFR-L3（n_sig=18，LOHO=0.385，AUROC=0.690）落入空隙
被拒答，而同靶点 L5 口径为黄档（n_sig=25，LOHO=0.316）。本任务用 ≥20 靶点
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
  DRUG_NULL_N=10,000、seed 42（`config.signature_params()` 入 JSON 可查）。
- 驱动：`scripts/l7f_panel/run_panel.py`（分片并行；签名落盘缓存带参数哈希，
  换参数/换源自动隔离；复用 L7e exp1 口径：真实后端
  provider_factory → SignatureEngine → DrugScorer，AUROC 用 mimic 分方向）。
- 四元组：n_sig（封顶前 FDR+KS 通过数）、LOHO（留一 hairpin Jaccard 最小值）、
  AUROC（自身金标准抑制剂，mimic 方向）、判档（RULE_VERSION 4.5 实测输出）。
- 与 L7e 阶段2 的口径一致性：CDK4/EGFR/MTOR/BRAF 四靶点两侧结果与
  `deliveries/L7e-stage2.md` §6.1 逐项核对（同参数哈希命中缓存即逐字节一致）。
- 阴性对照：20 个随机签名（50 up + 50 down，seed 42，null M=10,000）：
  (a) fdr_reversal<0.05 药物比例 <1%（exp1 口径）；
  (b) 走真实 `grade()` 判档必须全红（随机签名无 hairpin → LOHO=None → 红）。

## 4. 四元组总表（待数据回填）

（待填：21 靶点 × L3/L5 两侧的 n_sig/LOHO/AUROC/判档 4.5 总表）

### 4.1 与 L7e 阶段2 四靶点交叉核对

（待填：CDK4/EGFR/MTOR/BRAF 与 L7e-stage2 §6.1 一致性）

### 4.2 分布分析

（待填：(n_sig, LOHO) 散点数据 + AUROC 着色数据；空隙区靶点数量与 AUROC 质量；
L3 vs L5 分布移动）

## 5. 候选方案与对比矩阵（待数据回填）

候选（均只放宽黄档、从不收紧，结构上无降档；另附逐格单调性断言）：

| 方案 | 黄档核心条件（绿档不变：n_sig≥5 且 LOHO≥0.5） |
|---|---|
| current（4.5） | n_sig≥20 且 0.3≤LOHO<0.5 |
| A | n_sig≥5 且 0.3≤LOHO<0.5（空隙整体并入黄档） |
| B35 / B40 / B45 | n_sig≥20 时同 4.5；n_sig∈[5,20) 时要求 LOHO≥θ（θ=0.35/0.40/0.45） |
| C | 连续斜坡：LOHO ≥ max(0.3, 0.55−0.02×n_sig)（n_sig=5→0.45，10→0.35，≥13→0.3） |

单调性定义：固定 LOHO 时 n_sig 增大不得降档；固定 n_sig 时 LOHO 增大不得
降档。`analyze_results.py::check_monotonicity` 在 n_sig∈[0,60] ×
LOHO∈[0.30,1.00]（步长 0.005）网格逐格断言——**6 个方案全部 0 违规**
（本地已跑，脚本随分支提交）。

（待填：对比矩阵——各方案 × 两侧的判档分布、各档 AUROC 均值、
Spearman(档, AUROC)、空隙区救回清单与其 AUROC、TP53/MYC/LMNA 是否仍红、
阴性对照是否仍全红、L5 侧相对 4.5 的升/降档清单）

## 6. 阴性对照（待数据回填）

（待填：两侧药物 FDR 比例 max/mean；20 随机签名判档结果；各候选方案下
随机签名结构性仍红的论证——LOHO=None → 红，方案均不动该防线）

## 7. 推荐方案与理由（待数据回填）

## 8. 决策点答复建议（D-a ~ D-d，待数据回填）

- D-a 推荐方案与切点：
- D-b 黄档 n_sig 阈值 20 是否保留：
- D-c 空隙区理由文案措辞（面向研究者的指引）建议：
- D-d L5 口径是否同步调整 / 一套规则两口径共用：

## 9. 复跑与抽查入口

```bash
# 服务器产物：/home/keji/l3_tmp/l7f_results/
#   coverage_l3.json coverage_l5.json
#   panel_l3_shard*.json panel_l5_shard*.json（+ 同名 .log）
#   signatures_l3/ signatures_l5/（签名落盘缓存，文件名含参数哈希）

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
D:/mine_Anaconda3/python.exe -I scripts/l7f_panel/analyze_results.py \
  --l3 <本地l7f_results副本> --l5 <同上> --out analysis.json
```

## 10. 已知边界与风险

（待填：面板外推性、HDACi 非特异性、BRAF=MEK 金标准重叠等）

# L7e 阶段 2 交付：L3 签名数据源全量实施

- 任务：L7e 阶段 2（全量实施）｜ 分支：LMNA `feat/l3-signature`
- 基线：阶段 1 spike @ 7b90f24（报告 docs/design/L7e-spike-report.md）
- 提交：`33b1a8c`（实现+测试）→ `a2fda1c`（exp1 AUROC 方向修正）→ `4075a3a`（exp1 金标准掩码对齐修正+签名缓存）→ 本文档提交；服务器红线遵守：生产目录全程只读，写入仅 `/home/keji/l3_tmp/`，未重启/修改任何运行中服务，未安装依赖（复用 `~/miniconda3/envs/cmap`），大文件（*.npy、cache/）未入库。

## 1. 符号约定（不变）

- 样本内秩 1 = 表达最高；**KS > 0 = 敲低后上调**（进 up_genes），KS < 0 = 下调。
- 药物 XSum：`mimic = Σz(up) − Σz(down)`（正=模拟敲低），`score = −mimic`（高=逆转）。
- **exp1 AUROC 方向**：金标准抑制剂药理上模拟敲低，AUROC 用 **mimic 分**计算
  （与核验锚点 CDK4 0.844→0.964 同方向；reversal 分读出的是 1−AUROC 镜像，
  首轮跑出的 CDK4-L5 0.056 即镜像，已修正脚本并复跑）。
- NaN 剔除：L3 MAD=0 基因置 NaN → 秩矩阵配哨兵秩 0 → 凡在 null 池或目标样本中
  出现 NaN 的基因从签名（up/down/KS/p/FDR/LOHO top 集）中剔除，结果置 null 并计入
  `excluded_nan_genes`。无 NaN 的数据（L5/fixture）行为与旧版逐元素一致。

## 2. 改动文件（文件:行号）

| 文件 | 说明 |
|---|---|
| `backend/l3_robust_z.py:1-106`（新） | robust z 纯函数：`plate_robust_stats`（:36，median/MAD×1.4826 + scale floor = 同板 scale 中位数×0.01）、`resolve_control_stats`（:61，板→细胞系→全局三级回退）、`apply_robust_z`（:82，MAD=0→NaN）、`rank_columns_nanaware`（:91，NaN 剔除排名 + 哨兵 0）；常量 :27-33 |
| `backend/l3_provider.py`（重写，224 行） | L3Provider：读派生层；启动校验行列 ID 花名册 sha256 与 manifest 逐一一致、meta/npy 行数与顺序一致（:89-160），不一致 RuntimeError 拒绝启动；签名侧方法 :163-200；药物方法 NotImplementedError（:208-224） |
| `backend/composite_provider.py:1-98`（新） | CompositeProvider：签名侧→L3、药物侧→L5；启动时校验两侧 978 landmark 顺序一致（:37-46），日志打印两侧数据源（:48-51） |
| `backend/provider_factory.py:31-35` | `DATA_PROVIDER=l3` → CompositeProvider |
| `backend/config.py:131-141,161` | `L3_DERIVED_DIR`（env 可配）、`SIGNATURE_AGGREGATION`（l3→instance / 其他→modz）；`signature_params()` 加 `aggregation` 字段（`DATA_PROVIDER` 本就在）→ L3/L5 签名与药物缓存文件名隔离 |
| `backend/signature_engine.py:24,102,168-180,197-215,243-249,259-265,308-321,331-347` | NaN 剔除：秩缓存构建与目标排名走 `rank_columns_nanaware`；init 扫描池哨兵（:168-180）；剔除基因 KS 置 0 不进 top 集、BH 只对有效基因、字典/all_ks/all_p 置 null；新增 `excluded_nan_genes`/`n_excluded_nan_genes` 字段；target_median_z 抗 NaN |
| `backend/suitability.py:195-217,252-254` | `loho_jaccard_min` 加可选 `gene_valid_mask`（缺省 None = 旧行为） |
| `scripts/build_l3_derived.py:1-342`（新） | 全量构建：顺序流式扫描 65 GB gctx → robust z → 派生层 + manifest（源文件 sha256、花名册 sha256、参数、commit、耗时、QC 计数）；路径全部 env 可配（`L3_DERIVED_DIR` 等） |
| `scripts/l3_exp1_accuracy.py:1-261`（新） | 准确性实验（exp1 口径）：4 靶点 × L3/L5，金标准 AUROC（mimic 方向）、4×4 交叉、20 随机签名阴性对照 |
| `backend/tests/test_l3_stage2.py:1-444`（新） | 15 个单测（合成 4 板 × 20 基因，不依赖服务器） |
| `backend/tests/test_provider_l3.py`（重写） | 旧空壳测试作废；改测工厂返回 CompositeProvider、landmark 不一致拒启动、派生层缺失拒启动 |

## 3. D-a ~ D-d 实际选择（阶段 1 默认值，用户批准）

| 决策点 | 选择 | 实现位置 |
|---|---|---|
| D-a z 公式 | median / (MAD×1.4826) + **scale floor = max(1.4826×MAD, 同板 scale 中位数×0.01)** | `l3_robust_z.py:36-58` |
| D-b 对照 | 只用 `ctl_vector`（同板 ≥3 孔，否则回退同细胞系→全局，记 fallback_level） | `l3_robust_z.py:61-79`、`build_l3_derived.py` |
| D-c 聚合 | 实例级（每孔一样本，sig_id=inst_id） | `l3_provider.py`、build 脚本 |
| D-d MAD=0 | 该基因该板置 NaN；秩签名剔除（哨兵秩 0 + 签名级剔除 + 计数） | `l3_robust_z.py:91-106`、`signature_engine.py:197-215` |

补充拍板项（阶段 1 验收遗留）：KS null 池 = 同一份 L3 全量 trt_sh 池 448,737（秩矩阵 int16 0.88 GB，缓存于 LMNA_CACHE_DIR）；tiny-MAD 用 scale-floor（上文 D-a）。

## 4. 派生层构建结果（服务器实测）

- 命令：`cd /home/keji/l3_tmp/stage2 && ~/miniconda3/envs/cmap/bin/python -B scripts/build_l3_derived.py`
- 产物 `/home/keji/l3_tmp/derived/l3_v1/`：`l3_landmark.npy`（474,096×978 float32，1.85 GB）、`instance_meta.csv`、`col_ids.txt`、`row_genes.csv`、`manifest.json`
- 行数 474,096 = trt_sh 448,737 + 同板 ctl_vector 25,359（与阶段 1 估算一致）；板 1,467
- 耗时 **3.2–4.8 分钟**（页缓存热；冷盘估 10–30 min，与 spike 估算一致）；峰值内存 < 5 GB
- manifest：源 gctx sha256 `8aec42ec37836a8f…`（65.1 GB 实算）、行列花名册 sha256、参数、code_commit
- QC：回退 {L0: 473,513, L1: 583, L2: 0}；ctl<3 的板 162/1,467；NaN 行 344,060（72.6%）、NaN 基因-值 1,576,721（0.34%）、**出现过 NaN 的基因 250 个**（top：GAPDH 180,840、RPS6、MIF、FKBP4、DNAJA3——持家基因为主，与 spike 一致）
- 抽验：与 spike z（同公式无 floor）对 6 个实例 Pearson r = 1.000、秩相关 1.0000；|z| p99.9 = 112（spike 无 floor 时 246/max 2.6e5，floor 生效）
- L3Provider 实测：CDK4 210/11 hairpin、EGFR 680/20、MTOR 455/18、BRAF 689/14、LMNA 93/3——5 基因与 spike 逐一相同

## 5. pytest 输出

```
（本地，mini 夹具）       181 passed, 1 skipped   （含新 15+4 个 L7e 用例，全部通过）
（本地，24MB 完整夹具）   181 passed, 1 skipped   CDK4 234/0.587/绿 基线不变
```

- 新单测覆盖（任务卡 8 项全有）：robust z 手算对照、对照<3 回退（L1/L2 两级）、
  MAD=0→NaN 剔除、scale-floor 生效、trt_sh 精确过滤（cgs 诱饵排除）、
  L3/L5 缓存键不同、行列 ID 篡改/行数不一致拒绝启动、CompositeProvider 路由、
  引擎 NaN 剔除（excluded_nan_genes/up-down 不含/null 字段）。
- 回归：`DATA_PROVIDER=l5` 默认不变；旧测试全绿；完整夹具 CDK4 n_sig=234、
  LOHO=0.587、绿档不变（test_integrity 按夹具 expected 校验）。

## 6. 准确性实验（exp1 口径，服务器只读跑）

参数与现网 v2 生产一致：KS≥0.2、FDR<0.001、Bootstrap 100,000、每方向封顶 50、
DRUG_NULL_N=10,000、seed 42。药物侧两侧同为 L5 MODZ 中位数矩阵（19,811 药）。
金标准药物表 = `round2/verification/多基因测试-权威基准.md`（别名组精确匹配小写 pert_iname）。

两侧均用真实后端（`provider_factory → SignatureEngine → DrugScorer`）跑通；
签名经落盘缓存（`results/signatures_{l3,l5}/`）保证分析修正后复跑结果一致。
L3/L5 同靶点 AUROC 不再相同（CDK4 0.8187 vs 0.8155），掩码对齐修正生效。

### 6.1 四靶点自身抑制剂 AUROC（mimic 方向）与签名质量

| 靶点 | 侧 | n 样本 | n_sig | LOHO-min | 判档 | AUROC | 金标准在场 | 金标准最佳名次 |
|---|---|---|---|---|---|---|---|---|
| CDK4 | **L3** | 210 | 101 | 0.676 | 绿 | **0.819** | 3/6 | 121 |
| CDK4 | L5 | 71 | 83 | 0.636 | 绿 | 0.816 | 3/6 | 187 |
| EGFR | **L3** | 680 | 18 | 0.385 | **红** | **0.690** | 6/7 | 2365 |
| EGFR | L5 | 240 | 25 | 0.316 | 黄 | 0.728 | 6/7 | 1495 |
| MTOR | **L3** | 455 | 31 | 0.590 | 绿 | **0.956** | 8/10 | 14 |
| MTOR | L5 | 152 | 40 | 0.404 | 黄 | 0.997 | 8/10 | 3 |
| BRAF | **L3** | 689 | 24 | 0.655 | 绿 | **0.688** | 7/8 | 364 |
| BRAF | L5 | 231 | 25 | 0.562 | 绿 | 0.743 | 7/8 | 21 |

- 均值：L3 = 0.788，L5 = 0.821；绿档子集：L3 = 0.821（3 靶点），L5 = 0.780（2 靶点）。
- 锚点核对：EGFR-L5 AUROC 0.728 ≈ 权威基准文档锚点 0.754（旧核验）✓；
  金标准缺失集合两侧完全一致（ribociclib/abemaciclib/dinaciclib/dacomitinib/azd8055/
  ly294002/ci-1040 均不在 LINCS 药物矩阵，与阶段 1 覆盖核查一致）。
- L3 侧 4 靶点 excluded_nan 均 = 250（全局剔除集，见 §10-1）。
- EGFR-L3 红档机制：n_sig=18 < 黄档下限 20 且 LOHO 0.385 ∈ [0.3,0.5)，
  绿/黄核心条件均不满足，落入 `suitability.py` else 分支 → 红（规则表设计如此，见 §7）。

### 6.2 交叉对照 4×4（行=签名靶点，列=抑制剂集合，mimic 方向 AUROC）

L3：

| 签名＼抑制剂 | CDK4 | EGFR | MTOR | BRAF |
|---|---|---|---|---|
| **CDK4** | **0.819** | 0.589 | 0.962 | 0.579 |
| **EGFR** | 0.825 | **0.690** | 0.944 | 0.570 |
| **MTOR** | 0.601 | 0.563 | **0.956** | 0.495 |
| **BRAF** | 0.857 | 0.688 | 0.924 | **0.688** |

L5：

| 签名＼抑制剂 | CDK4 | EGFR | MTOR | BRAF |
|---|---|---|---|---|
| **CDK4** | **0.815** | 0.590 | 0.950 | 0.596 |
| **EGFR** | 0.610 | **0.728** | 0.772 | 0.654 |
| **MTOR** | 0.349 | 0.591 | **0.997** | 0.432 |
| **BRAF** | 0.728 | 0.852 | 0.678 | **0.743** |

- 特异性差值（自身 − 他靶点均值）：L3 = CDK4 +0.109 / EGFR −0.089 / MTOR +0.403 / BRAF −0.135；
  L5 = CDK4 +0.104 / EGFR +0.050 / MTOR +0.539 / BRAF −0.010。
- MTOR 列两侧普遍偏高：MTOR 金标准含 dactolisib/pi-103/wortmannin/torin 等
  PI3K-mTOR 双抑/广谱抗增殖药，对多数敲低签名都呈 mimic，属预期药理而非缺陷。
- BRAF 两侧对角线均不占优（L3 0.688 < EGFR 列 0.688 持平、CDK4 列 0.857）：
  BRAF 金标准多为 MEK 抑制剂（trametinib/selumetinib/pd0325901），通路下游效应
  与 EGFR/RAS 签名重叠，已知现象。

### 6.3 阴性对照（20 个随机签名，50 up + 50 down，seed 42，null M=10,000）

| 侧 | fdr_reversal<0.05 药物比例 max | mean | 判定（<1%） |
|---|---|---|---|
| L3 | **0.0000%** | 0.0000% | ✅ 通过 |
| L5 | **0.0000%** | 0.0000% | ✅ 通过 |

L3 null 池扩大 3 倍（448,737 vs 154,993）后 null 校准依然稳健，无误检膨胀。

### 6.4 运行开销（服务器实测）

- L3 侧总耗时 9,482 s（≈2.6 h）：bootstrap 10 万次在 448,737 池上逐靶点
  15–54 min（CDK4 917 s、EGFR 3,234 s、MTOR ~2,200 s、BRAF ~3,100 s）；
  秩矩阵从缓存加载（首次构建约 10 min，0.88 GB int16）。
- L5 侧总耗时 2,892 s（≈48 min）。
- 产物：`results/exp1_l3.json`、`results/exp1_l5.json`（含 up/down 基因表、
  金标准名次、top10 reversal、逐签名阴性对照比例）。

## 7. 判档阈值建议（只建议，不改默认值）

数据基础：§6.1 四靶点 L3/L5 并排 + §6.3 阴性对照。样本量仅 4 个靶点，
以下为保守建议，**生产默认阈值本次一律不动**。

1. **n_sig 5 / 20：建议维持。** L3 下 n_sig 分布双向移动（CDK4 83→101 增多、
   EGFR 25→18 / MTOR 40→31 / BRAF 25→24 减少），无系统性膨胀或萎缩；
   红线下限 5 与黄档下限 20 在 L3 两侧都没有出现"大面积误判"的证据。
2. **LOHO 0.3 / 0.5：建议维持。** L3 实例级签名 LOHO 在 3/4 靶点上升
   （CDK4 0.636→0.676、EGFR 0.316→0.385、MTOR 0.404→0.590、BRAF 0.562→0.655），
   与"实例级带来更多 hairpin×细胞系多样性 → 签名更稳"的预期一致；
   绿档线 0.5 在 L3 下反而更有区分度（3 绿 1 红 vs L5 2 绿 2 黄），无需放松。
3. **唯一观察到的边界翻转是规则表设计行为，不是阈值问题**：EGFR-L3
   （n_sig=18，LOHO=0.385）落入"n_sig∈[5,20) 且 LOHO∈[0.3,0.5)"的格子——
   绿档要求 n_sig≥5+LOHO≥0.5、黄档反而要求 n_sig≥20，该格子直接掉红。
   其 AUROC 0.690 并非不可用。L3 下 n_sig 整体略降，落进此格子的靶点会比
   L5 多。**建议（下一任务卡再议，本次不改）**：要么把黄档 n_sig 下限与绿档
   对齐到 5，要么显式把该格子定义为黄；需要用 ≥20 个靶点的面板重校准后再动。
4. **阴性对照两侧 0%**（阈值 <1%）：L3 大 null 池下判档所依赖的 KS/FDR
   与药物 null 均无校准漂移，支持阈值整体平移使用。
5. 若要量化重校准，建议后续实验：≥20 个有金标准抑制剂的靶点 × L3，
   统计各档位 AUROC/Recall@100，再决定 n_sig 黄档下限与 LOHO 线是否微调。

## 8. 验收逐条核对

| 任务卡条目 | 状态 | 证据 |
|---|---|---|
| 1 全量构建 + manifest | ✅ | §4；manifest.json 含源 sha256/花名册 sha256/参数/commit/耗时 |
| 2 L3Provider 签名侧 + 启动校验 | ✅ | `l3_provider.py`；篡改/缺失测试 test_l3_stage2.py 6 项 |
| 3 CompositeProvider + 工厂 | ✅ | `composite_provider.py`、`provider_factory.py:31-35`；日志两侧可见 |
| 4 缓存键隔离 | ✅ | `config.py:161` aggregation 字段；测试 test_cache_key_isolation_l3_vs_l5 |
| 5 单测全绿 | ✅ | §5 |
| 6 L5 回归 | ✅ | §5（完整夹具基线不变） |
| 7 准确性实验 | ✅ | §6 |
| 8 阈值建议 | ✅ | §7（未改默认阈值） |
| 符号约定 | ✅ | §1 |
| 红线 | ✅ | 生产只读；写仅 l3_tmp；零依赖安装；服务未动；大文件未入库 |

## 9. 主agent 验收命令

```bash
# 本地（一条）：核心单测 + 回归
cd backend && python -m pytest -q        # 期望 181 passed, 1 skipped

# 服务器（一条）：复现派生层核心数字（只读）
ssh -i ~/.ssh/lmna_deploy keji@10.39.15.238 \
  '~/miniconda3/envs/cmap/bin/python -c "
import json,numpy as np,pandas as pd
m=json.load(open(\"/home/keji/l3_tmp/derived/l3_v1/manifest.json\"))
meta=pd.read_csv(\"/home/keji/l3_tmp/derived/l3_v1/instance_meta.csv\",dtype=str)
print(m[\"qc\"][\"n_trt_sh\"], m[\"qc\"][\"n_rows_total\"], m[\"qc\"][\"fallback_counts\"], m[\"qc\"][\"nan_genes_any\"])
print(\"CDK4\", ((meta.pert_iname==\"CDK4\")&(meta.pert_type==\"trt_sh\")).sum())"'
# 期望：448737 474096 {'0': 473513, '1': 583, '2': 0} 250；CDK4 210

# 实验结果 JSON：/home/keji/l3_tmp/stage2/results/exp1_l3.json / exp1_l5.json
# 复跑实验（L3 侧约 30–60 min）：命令见 scripts/l3_exp1_accuracy.py 文档字符串
```

## 10. 发现但未处理的问题

1. **250 个基因被全局剔除**（NaN 出现在任一实例）：除持家基因外含 HIF1A、DNMT1、
   PCNA、CDC20、HSPD1 等有生物学意义的基因。这是"不得让 NaN 进秩签名"口径的代价：
   这些基因在所有 L3 签名中缺席（结果 null）。更细的替代（按目标样本/池分别掩码、
   每基因独立 N 的 KS）实现复杂度高一个量级，本期未做。
2. **scale floor 仍有残留极端值**：|z| p99.9≈112（个别板整体 MAD 极小，floor 随之低）。
   KS 秩免疫，不影响签名；如未来要用 z 值本身（如 target_median_z 展示）需注意。
3. **L5 缓存键变化**：`signature_params()` 新增 `aggregation` 字段后，L5 的哈希也变
   → 部署本分支后现有 L5 签名/药物缓存全部失效，需要重新预热（结果不变，仅缓存重建）。
   秩矩阵缓存文件名未变（v2.{n}），L5 的 154,993 池缓存可直接复用。
4. **L3 派生层落盘位置**：当前在红线目录 `/home/keji/l3_tmp/derived/l3_v1/`（1.9 GB）。
   生产化需用户批准迁至 `~/cmap_v2_data/derived/l3_v1/` 并设 `L3_DERIVED_DIR`（默认
   `$CMAP_DATA_DIR/derived/l3_v1` 已与此一致）。
5. **L3 上线需整套重算**（spike 报告 §7-4 复述）：判档与药物 null 的口径都随 null 池
   （448,737 vs 154,993）变化，不能 L3 签名 + L5 阈值混用；本交付只给阈值建议（§7）。
6. exp1 阴性对照 null 矩阵采用"同 seed 同尺寸 → 抽样序列逐位相同"的等价缓存
   （脚本内注释），数学上与 20 次独立调用 `DrugScorer.drug_null` 完全一致。

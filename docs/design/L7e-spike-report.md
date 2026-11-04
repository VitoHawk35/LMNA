# L7e · 阶段 1 可行性 spike 报告（L3 + 同板 ctl_vector 重算 robust z）

- 日期：2026-10-26；分支：`feat/l3-signature`；脚本：`scripts/l3_spike/`（01–05 + 03_merge，可在服务器 `~/miniconda3/envs/cmap/bin/python -B` 复跑，env 已有 h5py 3.16 / numpy 2.2.5 / pandas 2.3.3，未装任何依赖）。
- 数据：`/data2/wanggang/camp/level3/GSE92742_Broad_LINCS_Level3_INF_mlr12k_n1319138x12328.gctx`（已在服务器，**无需下载 52.4 GB**——设计文档 §1 的前提已过时，实测文件 65.1 GB 未压缩）。
- 红线遵守：全程只读生产数据；写入仅限 `/home/keji/l3_tmp/`（npz/json 产物不入库）；未重启/修改任何运行中服务；L5 重算用 `LMNA_CACHE_DIR=/home/keji/l3_tmp/l5cache`（秩矩阵用符号链接只读复用 `~/lmna_v2_cache`），`LINCS_INTEGRITY_MODE=off` 仅跳过启动自检。
- 口径：`pert_type == 'trt_sh'` 精确匹配；行/列 ID 全部取 gctx 内部 `0/META/ROW|COL/id`；KS null 池来自同一份 L3（2,000 实例随机背景，seed 42）；显著性参数与现网 v2 生产一致（KS≥0.2、FDR<0.001、Bootstrap 100,000、每方向封顶 50）。

## TL;DR

方案可行。**LMNA 在 L3 实例级口径下从 L5 的红档（n_sig=0）变为黄档（n=93，n_sig=74，LOHO 0.396）**，正是论文（Kort 2025）使用的口径；论文的 84 个 LMNA 实例 = L3 全量 93 经 is_gold/qc 过滤后的数量（已在 v1 zsvc 池实测核对为 84）。两个必须解决的口径风险：MAD=0 产生 NaN（0.34% 值，集中持家基因）和 tiny-MAD 导致 z 爆炸（最大 |z|≈2.6×10^5）。全量构建无需下载，顺序流式扫描预计 10–30 分钟、产物约 2.9 GB。

## 1. gctx 布局与读速（任务 1）

- `0/DATA/0/matrix`：`(1,319,138, 12,328)` float32，**行=实例、列=基因**，contiguous、无压缩（chunks=None, compression=None）。
- 行 ID：`0/META/ROW/id`（12,328 条 |S9，Entrez ID）；列 ID：`0/META/COL/id`（1,319,138 条 |S46，inst_id 形如 `CPC005_A375_6H_X1_B3_DUO52HI53LO:K06`）。978 个 landmark Entrez ID 全部在 ROW/id 中找到；本次提取的 24,535 个列 ID 零缺失。
- 读速实测：散布 400 行 7.3 s（seek 密集）；连续 400 行 0.009 s；排序散布 20,000 行 258 s（77.5 行/s，冷盘、1.5% 密度）；顺序扫描 28,380 行/s ≈ 1.4 GB/s（页缓存热；服务器 754 GB 内存，65 GB 文件可整体驻留缓存）。spike 实际提取 454 行/s（部分热）。

## 2. robust z 提取（任务 2）

- 选取：5 基因 trt_sh 实例 1,689 个 + 随机背景 2,000 个；所在板 1,089 块，板上 ctl_vector 20,846 孔。
- inst_info 计数：`trt_sh` 精确匹配 = 448,737，与 `startswith` **相同**——`.cgs/.css` 只存在于 L5 sig_info 层，inst_info 里没有（设计文档 §2.2 的"含 .cgs/.css"括注以此更正）；精确匹配仍是必须遵守的口径（sig_info 层有派生类型）。
- 回退（<3 孔 → 同细胞系 ctl → 全局）：L0=3,687，L1=2，L2=0。全部 shRNA 板中 162/1,467（11%）ctl<3，但本 spike 的目标+背景只命中 2 个实例。
- MAD=0/NaN → 置 NaN：共 12,460 个基因值（占 0.34%），2,713/3,689 实例（74%）至少含 1 个 NaN；集中在持家基因：GAPDH 41% 实例、RPS6 26%、MIF、FKBP4、DNAJA3（L3 量化值导致同板 ctl 全同 → MAD=0）。
- **新发现（tiny-MAD 爆炸）**：MAD 非零但极小时 z 爆炸——全局 |z| p99=16.0、p99.9=246、**max=261,559**；47% 实例至少含 1 个 |z|>50 的基因。KS 用样本内秩，对极端值天然免疫（秩相同），签名层面影响小；但 NaN→最低秩的约定会让 GAPDH/FKBP4 等持家基因假性进入 down 列表（已在 EGFR 的 L3 down 列表观察到），阶段 2 必须定策略。

## 3. 五基因签名 L3 vs L5（任务 3）

| 基因 | L3 n | L5 n | hairpin | L3 n_sig | L5 n_sig | L3 LOHO | L5 LOHO | L3 档 | L5 档 | target_ks (L3/L5) | up J | down J |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CDK4 | 210 | 71 | 11 | 141 | 83 | 0.770 | 0.636 | 绿 | 绿 | −0.590 / −0.730 | 0.333 | 0.639 |
| MTOR | 455 | 152 | 18 | 49 | 39 | 0.607 | 0.418 | 绿 | 黄 | —（非 landmark） | 0.138 | 0.279 |
| EGFR | 680 | 240 | 20 | 41 | 25 | 0.547 | 0.316 | 绿 | 黄 | −0.400 / −0.469 | 0.000 | 0.207 |
| TOP2A | 251 | 90 | 3 | 19 | 22 | 0.462 | 0.257 | 红 | 红 | −0.750 / −0.826 | 0.250 | 0.409 |
| LMNA | 93 | 27 | 3 | 74 | 0 | 0.396 | 0.111 | **黄** | **红** | —（非 landmark） | —（L5 无显著基因） | — |

- L3 实例数约为 L5 签名数的 2.8–3.4 倍，符合"论文口径样本约 3 倍于 L5"的预期；L3 判档普遍升一档（EGFR/MTOR 黄→绿，LMNA 红→黄）。
- L5 侧来源：CDK4/EGFR/MTOR 用 `~/lmna_v3_cache/signatures/*_b031a48b8a_*.json` 缓存（参数哈希与现网 v2 生产相同：KS 0.2 / FDR 0.001 / B=100,000 / ALGO 2）；TOP2A/LMNA 用本分支 backend（RULE_VERSION 4.5）读生产数据只读重算。
- 管线交叉验证（CDK4 缓存 vs 本分支重算）：n_sig 83 vs 86、LOHO 0.6364 vs 0.6322、up Jaccard 0.955、down Jaccard 1.000、同绿档——±3 个边界基因为 bootstrap 抽样序列差异，管线可复现。
- up/down 重叠除 CDK4 外偏低（EGFR up 完全不交）：L3 实例级 plate-z 与 L5 MODZ 口径差异的体现；换口径后签名与药物排序会变，上线必须整套重算（判档、药物 null），不能混用。

## 4. 与 v1 z 值相关性（任务 4）

v1 `_l4zsvc_shrna_z.dat`（978 × 376,415，同板 ctl_vector mean/std，ddof=1，三级回退）vs 本次 median/MAD robust z，逐 978 基因 Pearson r：

| 实例 | 角色 | r | 备注 |
|---|---|---|---|
| KDC005_A375_96H_X2_F1B4:C18 | LMNA 目标 | 0.885 | |
| ERGK002_VCAP_120H_X1_B2:L05 | CDK4 目标 | 0.922 | |
| ERGK002_VCAP_120H_X1_B2:L08 | MTOR 目标 | 0.922 | |
| EKW001_PC3_120H_X3_F1B3:P16 | 背景 | 0.917 | |
| EKW001_PC3_120H_X3_F1B3:G24 | 背景 | **0.055** | 已排查，见下 |

G24 排查：该实例我们的 z 有 9 个基因 |z|>10（tiny-MAD 爆炸，最小 −2,750），剔除这 9 个后 **r=0.934**，与其余实例一致；同板姊妹孔 P16 r=0.917。结论：行/列对应无误，r<1 的主因是口径差异（median/MAD vs mean/std）及 MAD 量化不稳定，不是映射错误。

## 5. 全量构建估算（任务 5）

行数：448,737 trt_sh + 25,359 同板 ctl_vector ≈ **474,096 行 × 978 landmark 列**。

| 项目 | 估算 | 依据 |
|---|---|---|
| 派生层磁盘 | z float32 1.85 GB + 秩 int16 0.93 GB + 元数据 ~0.05 GB ≈ **2.9 GB** | 474,096×978×4 B / ×2 B |
| 峰值内存 | **< 5 GB** | 20k 行块缓冲 ~1 GB + z 常驻 1.85 GB + ctl 统计 ~0.1 GB |
| 提取耗时 | 顺序流式全扫描（推荐）：**10–30 min**（热缓存 46 s，冷盘估 5–15 min + Python 开销）；排序散布读：冷盘 ~1.7 h（77.5 行/s）、热 ~17 min | 本 spike 实测 + v1 zsvc_build 全量实测 52 s（热） |
| z + 秩计算 | 分钟级 | v1 日志：376,415 样本 z+rank 全程 < 1 min（热） |
| 临时空间 | 无需 52.4 GB 下载/解压（数据已在服务器）；临时产物 < 5 GB | — |

## 6. LMNA 实例数 vs 论文 84

- L3（inst_info trt_sh 精确）LMNA = **93** 实例：9 个细胞系（VCAP 18 @120h；A549 15、HA1E/HCC515/HEPG2/HT29/MCF7/PC3 各 9、A375 6，均 @96h），3 条 hairpin。
- 论文 84 = **is_gold/qc 过滤后**的数量：v1 zsvc 池（is_gold 优先 + qc_pass）中 LMNA 实例实测恰为 **84**；被滤掉的 9 个 = HCC515:C18、HT29:O20、PC3:O20 三个孔 × 各 3 块重复板（QC 失败孔）。差异完全解释。
- L5 侧 LMNA 仅 27 个签名（MODZ 聚合后），n_sig=0、LOHO 0.111 → 红档；L3 口径 93 实例 → 黄档。L7e 对 LMNA 有实质收益。

## 7. 风险与建议（阶段 2 决策点）

1. **MAD 口径不稳（最高优先级）**：MAD=0 → NaN（0.34% 值，持家基因集中）+ tiny-MAD → z 爆炸（max 2.6×10^5）。签名层靠秩基本免疫，但 NaN→最低秩会让 GAPDH/FKBP4 假性下调。阶段 2 候选策略：scale floor（如 `max(1.4826×MAD, 同板 scale 中位数 × 0.01)` 或全局分位下限）、NaN 基因逐板剔除、或 MAD 低于阈值时回退 std（v1 口径）。需人工拍板。
2. **ctl<3 回退**：11% 的 shRNA 板 ctl<3；spike 只命中 2 个实例，回退链路（板→细胞系→全局）已验证可行，但全量时约 5 万实例会走 L1/L2，需在 QC 中计数。
3. **KS null 池**：spike 用 2,000 随机背景；全量应为全池 448,737（秩矩阵 int16 仅 0.88 GB，可行）。池构成变化会改变 p 值口径，判档阈值需在全量上重验。
4. **不要混用口径**：L3 签名 + L5 药物打分的 CompositeProvider 方案不变；L3 上线需同步重跑判档与药物 null（设计文档 §8.2-5 已有此条，spike 数据再次支持）。
5. MTOR/LMNA 非 landmark，target_ks 不可得（与 L5 一致），D1 防线 2 对这两基因天然不适用。
6. 建议阶段 2 直接做全量构建（10–30 min 机器时间）+ 5 基因全池重验，通过后再接 CompositeProvider。

## 附：复现方式

```bash
# 服务器上（全部产物落在 /home/keji/l3_tmp/）
cd /home/keji/l3_tmp/scripts   # = 本分支 scripts/l3_spike/
PY=~/miniconda3/envs/cmap/bin/python
$PY -B 01_probe_layout.py
$PY -B 02_extract_z.py
for g in CDK4 MTOR EGFR TOP2A LMNA; do
  $PY -B 03_l3_signatures.py --gene $g --out 03_l3_$g.json &
done; wait
$PY -B 03_merge.py
LMNA_BACKEND=/home/keji/l3_tmp/l5backend CMAP_DATA_DIR=/home/keji/cmap_v2_data \
LMNA_CACHE_DIR=/home/keji/l3_tmp/l5cache BOOTSTRAP_N=100000 FDR_THRESHOLD=0.001 \
KS_THRESHOLD=0.2 FAST_MODE_TOP_N=0 DATA_PROVIDER=l5 LINCS_INTEGRITY_MODE=off \
$PY -B 04_l5_signatures.py
$PY -B 05_compare.py
```

结果 JSON：`/home/keji/l3_tmp/results/01_probe.json`、`02_extract.json`、`03_l3_signatures.json`、`04_l5_summary.json`、`05_compare.json`。

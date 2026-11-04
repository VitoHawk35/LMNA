# task-L7f 交付说明（判档规则表 L3 口径重校准）

任务ID / 分支：L7f / `fix/L7f-grading-recal`（基线 main @ `fa836b2`，L7e 已合并）

交付物：

- `docs/design/L7f-规则表重校准.md` — 阶段1 重校准报告（§0-§10）+ 阶段2 实施记录（§11）
- `scripts/l7f_panel/` — 21 靶点面板定义与驱动/覆盖核查/分析/交叉核对/绘图脚本，
  `local_results/` 含全量分片结果、合并分析（analysis.json）与散点图
- `backend/suitability.py`、`backend/config.py` — RULE_VERSION 4.6 实施（阶段2）
- `backend/tests/test_suitability.py`、`backend/tests/test_integrity.py` — 测试更新与新增

## 阶段1：重校准（面板 + 方案对比）

- 问题：L3 口径下 n_sig∈[5,20) 且 LOHO∈[0.3,0.5) 的"空隙区"落入 else 判红
  （4.5 黄档要求 n_sig≥20），实测 EGFR-L3（18/0.385/AUROC 0.690）被误拒答。
- 面板：21 靶点（基准 10 + LMNA + 扩展 10）× L3/L5 两侧全量重跑
  （L3 12.4 CPU·h / L5 4.1 CPU·h，56 核服务器，墙钟约 2.5h），
  四元组与金标准 AUROC 见报告 §4；与 L7e 阶段2 四靶点交叉核对
  L3 4/4 逐位一致、L5 3/4 一致（MTOR-L5 AUROC 4e-4 尾差已注明原因）。
- 关键发现：L3 空隙区 6 靶点内 LOHO 与 AUROC **不单调**（LOHO=0.333 簇
  AUROC 0.89/0.79/0.69 反而最高）——任何"空隙内再加 LOHO 门槛"的方案
  都会选错对象，故推荐并获拍板 **方案 A：黄档 n_sig 下限 20→5**。
- 6 候选方案单调性网格断言全过、两侧零降档、20 随机签名阴性对照全红。
- 用户拍板：D-a/D-b=方案 A；D-c=升黄者谨慎文案；D-d=一套规则两口径共用；
  TP53/MYC 接受现状（L3 下绿），"不可成药"语义由注释层另开任务承载。

## 阶段2：实施（RULE_VERSION 4.6）

- `SUITABILITY_YELLOW_MIN_SIG` 默认值 20→5；`RULE_VERSION="4.6"`；
  黄档理由文案分两支：升黄者（n_sig<20）给「命中信心低于典型黄档…
  补一种正交证据」，常规黄档文案不变；4.5 的「未满足绿档或黄档条件」废弃。
- 判档变化只发生在原空隙区：L3 侧 EGFR/HDAC1/ALK/FGFR1/CDK2/PIK3CA、
  L5 侧 PLK1/MET 由红升黄；其余 34 个靶点-侧不变。
- 测试：mini 夹具与完整夹具两遍均 **190 passed / 1 skipped / 0 failed**
  （基线 181 → +9：7 个 L7f 新测试 + 2 行新边界参数；唯一 skip 为既有 D3 项）。
  新增测试含 n_sig/LOHO 双维单调性网格、4.6 对 4.5 全网格无降档、
  LOHO=None 恒红、升黄者/常规黄档文案、TP53/MYC 现状锁定。
- 测试环境：服务器 `~/miniconda3/bin/python`（base，pytest 9.0.2），
  部署点 `/home/keji/l3_tmp/l7f_stage2/`；完整夹具上传至
  `/home/keji/l3_tmp/fixtures_l0/`（npz md5 与本地一致）。

## 部署注意（留给后续部署任务）

已缓存签名的 `qc` 记录计算时刻的 4.5 判档；4.6 上线后旧缓存不会自动重判，
部署时应清理签名缓存或接受新旧档位并存的过渡期。本次未部署、未重启任何
生产服务（8001/8003/8004/8007/8084/8085/8086 未触碰），分支未合并 main。

## 红线自查

- 服务器只读：写入仅 `/home/keji/l3_tmp/`（l7f、l7f_results、l7f_stage2、
  fixtures_l0、l7f_cache*）；未装依赖；未重启/修改任何运行中服务。
- 大文件未入库：入库最大文件 31KB（analysis.json）；服务器侧大数据
  （签名缓存、分片日志）留在 `/home/keji/l3_tmp/`。
- 只推分支 `fix/L7f-grading-recal`，未合并 main。

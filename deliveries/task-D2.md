# task-D2 · 裁剪夹具入库（R9）

任务ID / 分支 / 基线提交：**D2 / `feat/D2-mini-fixture` / `origin/main` 2e371c2**

目标：从 24MB 回归夹具截出 ≤3MB 的 mini 版提交进仓库；默认（不设任何环境
变量）pytest 使用裁剪版，`LMNA_FIXTURE_DIR` 指向完整夹具时运行完整回归；
补上 ABHD4 单 hairpin 基因，让 L3 的 422 测试在裁剪版上也能跑。

## 改动文件

| 文件 | 内容 |
|---|---|
| `backend/tests/make_mini_fixture.py` | 新增：裁剪脚本。从完整夹具选列、写 mini 数据文件、按完整夹具同法生成 mini expected（固定种子 42，B=1000、封顶 50、每靶点新建 engine） |
| `backend/tests/data/mini_fixture/` | 新增：mini 夹具 5 个文件（npz / sh.tsv / cp.tsv / meta.json / expected.json），总计 **2.36 MB**（硬约束 ≤3MB） |
| `backend/fixture_provider.py` | npz 含 `value_scale` 键时加载后乘回（mini 按 int16 milli-z 存储）；完整夹具无该键，乘子 1.0，行为不变 |
| `backend/tests/conftest.py` | 未显式设置 `LMNA_FIXTURE_DIR` 时默认回落到 `backend/tests/data/mini_fixture/`；显式设置后语义完全不变；report header 标注「默认 mini」 |
| `backend/tests/test_fixture_provider.py` | 形状断言从硬编码 `>3000` 改为与夹具 meta 的 `n_sh`/`n_cp` 一致（完整夹具 3482/3155、mini 1085/300 都通过；原断言只对完整夹具成立） |
| `backend/tests/test_suitability.py` | gof top 排序断言改为按实现契约 `(fdr_mimic, score)` 升序（完整夹具上恰好等同纯 score 升序；mini 药物池小、FDR 分档不同，纯 score 断言不成立。实现契约见 `drug_scorer._xsum_score`，完整夹具上新旧断言均通过） |

只加不删：未动 `main.py` / `signature_engine.py` / `drug_scorer.py` /
`suitability.py` / `config.py`；`.gitignore` 未改（现有规则不排除
`backend/tests/data/mini_fixture/`）。

## 裁剪规则（固定种子 42）

- 978 个 landmark 基因全部保留。
- shRNA 列（共 **1085**）：4 个基准靶点全部样本（CDK4 86 / TOP2A 96 /
  EGFR 150 / MTOR 150，以完整夹具 meta 为准）+ ABHD4 全部 3 个样本
  （1 个 hairpin，用于 L3 数据门槛与 /compute 422 测试）+ 背景
  `np.random.default_rng(42)` 无放回抽 600 条。
- 药物列（共 **300**）：4 个靶点已知抑制剂的并集 **88 个全部包含**
  （与完整夹具 meta 逐一核对，无缺失）+ 其余药物同一种子补 212 个。
- 存储：矩阵按 int16 千分位 z（milli-z）存进 npz，附带
  `value_scale=0.001`，加载时乘回。数值误差 ≤0.0005，z 语义不变
  （`target_median_z` 等不受影响）。float32 原样存储需 ~5.0MB 超过
  3MB 硬约束，milli-z 后 npz 为 2.26MB。

## expected 值

`lmna_fixture_expected.json` 用与完整夹具相同的生成方式（修正后的算法、
固定种子 RANDOM_SEED=42、BOOTSTRAP_N=1000、FAST_MODE_TOP_N=0、
MAX_GENES_PER_DIRECTION=50、每靶点新建 `SignatureEngine`）在 **mini
数据本身**上重新生成；背景池变小后数值与完整夹具的 expected 不同，
二者不混用（各自随自己的夹具目录走）。

## 自测验收（任务卡 D2）

- [x] `backend/tests/data/mini_fixture/` 总大小 ≤3MB：
  `du -sh` = **2.3M**（`du -sb` = 2360343 字节）。证据：
  本地 `deliveries/task-D2/du-mini.txt`。
- [x] 不设任何环境变量，pytest 夹具相关测试 0 跳过、0 失败：
  本机 worktree 默认 run **129 passed, 1 skipped**（唯一 skip 是
  Table S1 缺失的既有项，与夹具无关）。证据：
  本地 `deliveries/task-D2/pytest-mini-default.log`。
  干净 clone（`git clone` 仓库 + checkout 本分支，全新目录、不设任何
  环境变量）：**129 passed, 1 skipped**，夹具相关测试 0 跳过。证据：
  本地 `deliveries/task-D2/pytest-clean-clone.log`。
- [x] `LMNA_FIXTURE_DIR` 指向 24MB 完整夹具：**129 passed, 1 skipped**
  （与基线一致；唯一 skip 同为 Table S1 既有项）。证据：
  本地 `deliveries/task-D2/pytest-full-fixture.log`。
- [x] CDK4 差异量化（见下节）。

## CDK4 在裁剪版 vs 完整夹具的差异（B=1000，固定种子）

| 指标 | 完整夹具 | mini 夹具 | 差异 |
|---|---|---|---|
| n_sig | 234 | **230** | −4（−1.7%） |
| LOHO (loho_jaccard_min) | 0.587 | **0.5873** | +0.0003（几乎不变；LOHO 只依赖 CDK4 自身样本，全部保留） |
| target KS | −0.7457 | −0.7457 | <0.0001 |
| 判档 | 绿 | 绿 | 不变 |

n_sig 变小是预期内的背景池效应（bootstrap null 池 3482→1085 列）；
milli-z 量化的额外贡献上限约 |ΔKS|≤0.02（列内秩跳动 ≤18/978），
已在容差内。TOP2A 仍红档（LOHO 0.286 vs 参考 0.290±0.05）、
EGFR 仍绿档（LOHO 0.609 vs 参考 0.532±0.10，mini 的 milli-z 秩噪声使
top-k 边界换了约 3 个基因，仍在放宽容差内）。

## 复现 mini 夹具（生成命令）

```
python backend/tests/make_mini_fixture.py \
    --full-dir /path/to/24MB_fixture \
    --out-dir  backend/tests/data/mini_fixture
```

完整夹具不入库；本机数据源在 `D:\agent-workspace\deliveries\task-L0\fixtures\`。

## 主agent验收命令

```bash
# 干净 clone + 默认 mini（不设任何环境变量）
git clone <LMNA 仓库> lmna-d2-check && cd lmna-d2-check && \
git checkout feat/D2-mini-fixture && \
du -sh backend/tests/data/mini_fixture && \
cd backend && python -m pytest tests -q
# 期望：du ≤ 3.0M；129 passed, 1 skipped（skip 为 Table S1 既有项）

# 完整夹具回归
LMNA_FIXTURE_DIR=/path/to/24MB_fixture python -m pytest tests -q
# 期望：129 passed, 1 skipped
```

实验 V-D2（干净 clone）已由子agent在 `D:\agent-workspace\deliveries\task-D2\clean-clone\`
预先复现一遍，日志见同目录 `pytest-clean-clone.log`。

## 待人工确认项（🧑‍⚖️）

1. mini 夹具的存储格式为 int16 milli-z + `value_scale`（数值误差 ≤0.0005，
   为压进 3MB 硬约束的必要手段；float32 原样需 ~5MB）。若要求 mini 与
   完整夹具逐位一致，需要放宽大小约束或改存列内秩（会改变
   `target_median_z` 的 z 语义）。
2. `test_suitability.py` 的 gof 排序断言从「纯 score 升序」改为实现契约
   「(fdr_mimic, score) 升序」（原断言只在完整夹具上碰巧成立）。如需保持
   原断言，可讨论是否应改 `drug_scorer` 的 gof 排序（超出本任务范围，未动）。

## 发现但未处理项

- 无（D1 的完整性防线与本任务并行，未依赖、未包含其改动）。

# task-D1 · 数据完整性防线（LMNA 侧）

任务ID / 分支 / 基线提交：`D1` / `feat/D1-integrity` / `origin/main` @ `2e371c2`

## 结论摘要

1. **防线1（启动逐 ID / 指纹比对）已建立**：新增共享模块 `backend/lincs_integrity.py`
   （与 cmap-l1000 `app/core/lincs_integrity.py` 内容完全一致，文件头已注明同步要求），
   接入 `l5_provider.py` 初始化。`LINCS_INTEGRITY_MODE=gctx|fingerprint|off`，
   **默认 fingerprint**（任务包 Q2 默认建议）；任何不一致抛 `RuntimeError` 拒绝启动，
   错误信息给出第一个不一致位置（gctx 模式直接给出；fingerprint 模式给出诊断命令）与修复命令。
2. **指纹工具链**：`scripts/fix_col_names.py` 新增 `--write-fingerprint`，
   在花名册与 GCTX 一致后写出 `integrity.json`（行/列 ID 列表 sha256、矩阵形状、
   3 列抽样数值 sha256）；花名册未修复时拒绝写指纹。
3. **R11 已顺带修复**：`config.py` 不再硬编码 `N_GENES/N_SIGS`，
   改为 integrity.json → 花名册行数+矩阵字节数交叉验证 → L1000 名义默认（数据不在本机时回退）。
4. **防线2（生物学自检）已建立**：`backend/integrity_selfcheck.py` 启动后后台对哨兵基因
   （默认 CDK4、PCNA、MYC，`LINCS_SENTINEL_GENES` 可覆盖；landmark 且 hairpin≥3 才计入）
   计算目标基因自身 KS，阈值 −0.3；2/3 以上不通过 → `/api/health` 返回
   `integrity: suspect`，前端顶部显示黄色横幅「数据自检未通过，结果可能不可靠」。
5. **判档规则 4.5**：landmark 靶基因自身 KS > 0 时最高黄档，
   理由「敲低后目标基因自身未下降，敲低可能未生效或数据有误」；`RULE_VERSION = "4.5"`。
6. **只加字段**：`/api/health` 新增 `integrity` / `integrity_mode` 两个字段，旧字段不变。

## 改动文件

| 文件 | 改动 |
|---|---|
| `backend/lincs_integrity.py` | 新增。共享模块：模式选择、花名册逐 ID 比对、指纹构建/校验、GCTX 比对、`check_startup` 入口。Python 3.8 兼容 |
| `backend/l5_provider.py` | 初始化时调用 `check_startup`（在旧"字典序哨兵"之前），label 固定为 `row_gene_ids.csv`/`col_sig_ids.csv` 以兼容 L8 测试断言 |
| `backend/config.py` | 删除 `N_GENES = 12328 / N_SIGS = 473647` 硬编码，改 `_resolve_matrix_dims()`（指纹 → 花名册+矩阵大小 → 回退默认） |
| `backend/integrity_selfcheck.py` | 新增。哨兵自检：`compute_self_ks` / `run_self_check` / 后台线程 / 状态查询 |
| `backend/main.py` | startup 事件启动后台自检；`/api/health` 新增 `integrity`、`integrity_mode`（get_mode 异常容错为 "invalid"） |
| `backend/suitability.py` | `RULE_VERSION = "4.5"`；自身 KS 计算前移；绿档 + landmark 自身 KS > 0 → 降黄档并追加理由 |
| `frontend/index.html` | 顶部黄色横幅 `#integrityBanner`，页面加载时及 15s 后各查一次 `/api/health`，`integrity === 'suspect'` 时显示 |
| `scripts/fix_col_names.py` | 新增 `--write-fingerprint`（可与 `--check` 或修复操作组合；花名册与 GCTX 不一致时拒绝写指纹） |
| `backend/tests/test_integrity.py` | 新增，37 个用例（见下） |
| `backend/tests/test_l8_col_order.py` | 夹具夹带 integrity.json；`test_sorted_col_names_read_wrong_columns` 显式 `LINCS_INTEGRITY_MODE=off`（该用例故意复现旧行为） |
| `deliveries/task-D1.md` | 本文件 |

## 自测验收（任务卡 D1 逐条）

### [x] 新测试 test_integrity.py 覆盖 5 种花名册（正确/字母排序/随机打乱/10%互换/只错1位），后4种全部拒绝，行列各测一遍

`backend/tests/test_integrity.py::test_roster_tampering`：
5 种状态 × 行/列 × **gctx + fingerprint 两种模式** = **20 个用例**（要求 10 个，超额覆盖），
正确 4 例通过、其余 16 例全部 `RuntimeError`。另有：

- `test_gctx_mode_reports_first_mismatch_position`：错误信息含「第 5 行」与修复命令；
- `test_missing_one_row_rejected`：行花名册少一行 → 拒绝（两种模式）；
- `test_trailing_blank_line_tolerated_with_warning`：末尾空行按约定容忍 + WARNING（不静默）；
- `test_off_mode_passes_with_warning`：off 放行但 WARNING「仅供测试」；
- `test_invalid_mode_rejected`：非法模式取值 fail safe。

输出：`37 passed`（本地证据 `D:\agent-workspace\deliveries\task-D1\lmna_pytest_full.txt`）。

### [x] 指纹模式下矩阵被换成同形状文件时拒绝启动

`test_matrix_swap_same_shape_rejected`：同形状不同数值矩阵覆盖后，
`check_startup(fingerprint)` 抛 `RuntimeError`（3 列抽样数值哈希不一致）。

### [x] 夹具上 CDK4 结果不变（234 / 0.587 / 绿）；伪签名判黄档

`test_fixture_cdk4_unchanged_and_fake_signature_yellow`（BOOTSTRAP_N=1000 固定参数）：

- `n_sig == 234`、`loho_jaccard_min ≈ 0.587`（±0.05）、`qc.grade == "green"`、
  `rule_version == "4.5"`、`ks_scores["CDK4"] < -0.3` —— 全通过；
- 同一签名把 CDK4 自身 KS 改为正值后重判 → `yellow`，理由含「敲低可能未生效或数据有误」。

`test_fixture_sentinel_self_check_ok`：夹具上哨兵自检 `status == "ok"`，
CDK4 `self_ks < -0.3`（PCNA/MYC 不在夹具 shRNA 表中，按设计跳过）。

### [x] LMNA 现有测试全绿

夹具下 `pytest -q`：**166 passed, 1 skipped**（基线 129 passed 1 skipped + 新增 37）。
证据：`D:\agent-workspace\deliveries\task-D1\lmna_pytest_full.txt`。

## 额外证据

- **服务冒烟**：`DATA_PROVIDER=fixture LINCS_INTEGRITY_MODE=off uvicorn main:app --port 8123`，
  启动后数秒 `/api/health` 返回
  `{"status":"ok","provider":"fixture",...,"integrity":"ok","integrity_mode":"off"}`。
- **行错位演示（V-D1b 预演）**：打乱 FixtureProvider 行花名册后 `run_self_check(["CDK4"])` →
  `status: suspect`，CDK4 `self_ks = -0.166`（不再 < −0.3）。
  配合规则 4.5（自身 KS 不再显著为负时绿档被封顶），行错位下 CDK4 不再是绿档。
- **fix_col_names 端到端**（tiny GCTX + 矩阵，本地证据目录 `D:\agent-workspace\deliveries\task-D1\e2e_data\`）：
  - `--check --write-fingerprint` 写出 `integrity.json` 后 `check_startup(fingerprint)` 通过；
  - 打乱花名册后同命令 exit 1：「拒绝写指纹：当前花名册与 GCTX 顺序不一致」。
- **两份共享模块一致**：`diff backend/lincs_integrity.py app/core/lincs_integrity.py`（cmap worktree）无差异。

## 部署注意（重要）

- 默认 `fingerprint` 模式下，**数据目录必须有 `integrity.json`，否则 L5 服务拒绝启动**。
  服务器部署窗口由人执行（数据已修复的前提下）：

  ```bash
  python scripts/fix_col_names.py --data-dir ~/cmap/cmap_data --check --write-fingerprint
  ```

  该命令只写 `integrity.json`，不改数据文件；回滚 = 删除 `integrity.json` 并设
  `LINCS_INTEGRITY_MODE=gctx`（或临时 `off`，会有 WARNING）。
- 哨兵列表、阈值可用环境变量调整：`LINCS_SENTINEL_GENES`、`LINCS_SELF_KS_THRESHOLD`、
  `LINCS_SENTINEL_MIN_HAIRPINS`。

## 主agent验收命令

```bash
cd <LMNA worktree>/backend && \
  LMNA_FIXTURE_DIR='D:\agent-workspace\deliveries\task-L0\fixtures' \
  D:\mine_Anaconda3\python.exe -m pytest tests -q
# 期望：166 passed, 1 skipped（其中 tests/test_integrity.py 37 个用例全过；
# test_fixture_cdk4_unchanged_and_fake_signature_yellow 锁定 234 / 0.587 / 绿 + 伪签名黄档）
```

## 待人工确认项

- 🧑‍⚖️ Q2 已按任务包默认建议实现为 **fingerprint**；如需改 gctx 只需设置环境变量，无需改代码。
- 哨兵基因默认值 CDK4/PCNA/MYC 与阈值 −0.3、2/3 比例如需调整，告知后可改默认值
  （当前均可由环境变量覆盖，不改代码）。

## 发现但未处理项

- `integrity_mode` 在 `fixture` provider 下如实反映环境变量（fixture 不跑防线1），
  生产 L5 下防线1 不过则服务根本起不来——这是预期语义。
- 自检状态仅存内存，重启进程即重置（与任务卡"启动后自检"语义一致）。

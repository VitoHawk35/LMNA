# task-L0 · LMNA 测试脚手架 + 夹具重建

任务ID / 分支 / 基线提交：`L0` / `fix/L0-test-scaffold` / `origin/main` @ `315f965`

## 改动文件（文件:行号范围）

| 文件 | 行号 | 改动 |
|---|---|---|
| `backend/config.py` | 33-34 | `CACHE_DIR` 支持 `LMNA_CACHE_DIR` 环境变量，makedirs 保留 |
| `backend/data_provider.py` | 39-51 | 新增抽象方法 `get_all_shrna_samples()` |
| `backend/l5_provider.py` | 110-111 | 实现 `get_all_shrna_samples()`（返回 `_shrna_df.copy()`） |
| `backend/l3_provider.py` | 35-36 | 实现占位（`NotImplementedError`） |
| `backend/provider_factory.py` | 1-36 | 新增 `create_provider(kind=DATA_PROVIDER)`：l5/l3/fixture，未知值 `ValueError` |
| `backend/fixture_provider.py` | 1-182 | 新增 `FixtureProvider`，实现全部 9 个抽象方法 + `get_all_shrna_samples()`；`get_expression_matrix` 同时支持 shRNA/化合物 sig_id |
| `backend/main.py` | 18-21, 41, 64 | 改用 `create_provider()`；health 的 provider 字段改为 `DATA_PROVIDER` |
| `backend/task_queue.py` | 16-20, 36-37, 163-188 | `_build_provider` 改调 `create_provider`；新增 `LMNA_TASK_INLINE=1` 同进程执行分支 |
| `backend/signature_engine.py` | 34 | `provider._shrna_df` → `provider.get_all_shrna_samples()` |
| `backend/requirements-dev.txt` | 1-4 | 新增 pytest、httpx（`<0.28`，见下） |
| `backend/tests/conftest.py` | 1-56 | import 后端模块前设置 `LMNA_CACHE_DIR`/`DATA_PROVIDER=fixture`/`LMNA_TASK_INLINE=1`/`FAST_MODE_TOP_N=0`/`BOOTSTRAP_N=200`；后端加入 sys.path；夹具缺失时依赖夹具的测试 skip |
| `backend/tests/test_core_pure.py` | 1-156 | 纯函数/配置/工厂/抽象接口/排名缓存测试 |
| `backend/tests/test_fixture_provider.py` | 1-103 | FixtureProvider 9 个接口测试 |
| `backend/tests/test_api_health.py` | 1-65 | health/genes/status/404 测试 |
| `backend/tests/test_task_inline.py` | 1-33 | inline 任务同步执行测试 |
| `backend/tests/test_signature_fixture.py` | 1-45 | 夹具上跑通 SignatureEngine |
| `backend/tests/make_fixture.py` | 1-387 | 夹具重建脚本（可重复执行，纯流式输出） |

## 夹具重建

**数据源：LINCS2020 beta Level5（服务器本地只读数据）**

- 目录：`/data2/wanggang/camp/level5/`
  - `siginfo_beta.txt`
  - `GSE92742_Broad_LINCS_gene_info.txt.gz`（978 landmark 基因）
  - `level5_beta_trt_sh_n238351x12328.gctx`
  - `level5_beta_trt_cp_n720216x12328.gctx`
- 化合物靶点注释：Drug Repurposing Hub `repurposing_drugs_20200324.txt`（脚本内下载到内存，530KB）。
- 生成脚本：`backend/tests/make_fixture.py`（随分支提交，不含数据）。
- 产物：`lmna_fixture.npz`（gene_symbols 978、sh_matrix 978×3553、cp_matrix 978×3155）、`lmna_fixture_sh.tsv`、`lmna_fixture_cp.tsv`、`lmna_fixture_meta.json`，共约 24MB。
- 本地路径（不入 git）：
  `D:\agent-workspace\deliveries\task-L0\fixtures\`
  使用方式：`set LMNA_FIXTURE_DIR=D:\agent-workspace\deliveries\task-L0\fixtures`
- 服务器操作仅为只读取数：脚本通过 `ssh` 的 stdin 传入、结果 tar 从 stdout 流回本地，**未在服务器落盘、未改缓存、未装依赖、未重启服务**。

### 为什么没有用任务推荐的 GSE92742 `fast_matrix.npy`

1. `cmap_data/col_sig_ids.csv` 是**按 sig_id 排序**后的列表，而 `fast_matrix.npy` 的列顺序是 **GCTX 的 COL 顺序**（已用 `level5`/`GSE92742` GCTX 逐列核对：`fast[:,0] == gctx[0, rows]`，但 `col_sig_ids[0]` 对应的是另一列）。按 `col_sig_ids` 取列会取到错误签名。
2. 实测 GSE92742 的 `trt_sh` 自身敲低信号很弱（CDK4 18 个 landmark 样本平均自身 z ≈ +0.04，rank ≈ 483/978），无法复现参考表。
3. LINCS2020 beta Level5 的样本数与参考表完全吻合（CDK4 86、TOP2A 96、EGFR/MTOR 取前 150），且复现出参考的 KS 量级与 LOHO Jaccard，故采用 beta Level5。

### 四靶点实测 vs 参考（BOOTSTRAP_N=1000、FDR<0.05、|KS|>0.2、每方向最多 50 基因）

| 靶点 | 样本（实测/参考） | hairpin（实测/参考） | 显著基因数（实测/参考） | 靶基因自身 KS（实测/参考） | LOHO Jaccard 最小（实测/参考） | 判档（实测/参考） |
|---|---|---|---|---|---|---|
| CDK4 | 86 / 86 | 7 / 7 | 240 / 234 | **+0.746** / −0.746 | 0.538 / 0.587 | 绿 / 绿 |
| TOP2A | 96 / 96 | 3 / 3 | 100 / 93 | **+0.837** / −0.837 | 0.290 / 0.290 | 红 / 红 |
| EGFR | 150 / 150 | 15 / 19 | 41 / 36 | **+0.528** / −0.460 | 0.542 / 0.532 | 绿 / 绿 |
| MTOR | 150 / 150 | 18 / 18 | 87 / 55 | 非 landmark / 非 landmark | 0.525 / 0.549 | 绿 / 绿 |

结论：样本数、KS 量级、LOHO 稳定性、判档方向均与参考一致。**KS 符号与参考相反**（靶基因下调时本实现给出正 KS，并被归入 `up_genes`），这是仓库现有的符号约定问题，正好是 task-L1 的范围，L0 未修改。完整实测见 `D:\agent-workspace\deliveries\task-L0\validation.json`。

## 测试

新增测试：

- `test_core_pure.py`：CACHE_DIR 可配置、测试环境默认值、未设置 `DATA_PROVIDER` 时默认仍为 `l5`、未知 provider 抛 `ValueError`、抽象接口含 `get_all_shrna_samples`、KS 极值、BH 输出范围、排名缓存走公共接口（不再依赖 `_shrna_df`）。
- `test_fixture_provider.py`：978 基因、矩阵形状、两表 sig_id 查询、未知 sig_id、`get_lm_gene_indices`、vehicle `NotImplementedError`、药物名映射、四靶点抑制剂元数据。
- `test_api_health.py`：`/api/health` 200 且 `available_genes >= 4`、`/api/genes`、`/api/genes/CDK4/status`、未计算签名的 404。
- `test_task_inline.py`：`LMNA_TASK_INLINE=1` 时同进程同步调用 worker，不创建进程池。
- `test_signature_fixture.py`：夹具上 `SignatureEngine.compute_signature("CDK4")` 跑通。

`pytest -q`（**无**夹具，`LMNA_FIXTURE_DIR` 未设置）：

```
ssss.........sssssssss.                                                  [100%]
10 passed, 13 skipped in 1.19s
```

`pytest -q`（设置 `LMNA_FIXTURE_DIR`）：

```
.......................                                                  [100%]
23 passed, 2 warnings in 2.46s
```

（警告来自 starlette/httpx 的 DeprecationWarning，不影响结果。）

## 验收逐条核对

- [x] `cd backend && pytest -q` 在**没有**夹具时能跑：10 passed, 13 skipped（纯函数通过，夹具测试 skip）。
- [x] 设置 `LMNA_FIXTURE_DIR` 后 `TestClient(app).get("/api/health")` 返回 200，`available_genes >= 4`（实测 `available_genes=1971`，≥4）。
- [x] 未设置 `DATA_PROVIDER` 时行为与原来一致：`config.DATA_PROVIDER == "l5"`，`create_provider.__defaults__[0] == "l5"`。
- [x] 缓存目录可配置：`LMNA_CACHE_DIR` 生效，测试全部写入临时目录。
- [x] `create_provider` 三种类型 + 未知值 `ValueError`。
- [x] `FixtureProvider` 实现 9 个抽象方法 + `get_all_shrna_samples`，`get_expression_matrix` 支持两类 sig_id。
- [x] 去掉 `signature_engine.py` 对 `_shrna_df` 的私有属性依赖。
- [x] `LMNA_TASK_INLINE=1` 同步执行，否则进程池。
- [x] 夹具约 24MB，未提交进仓库（用 `LMNA_FIXTURE_DIR` 指向）。

## 待人工确认（🧑‍⚖️）

1. **D10 / 夹具存放**：夹具（24MB）当前不入 git，仅在本地 `D:\agent-workspace\deliveries\task-L0\fixtures`。后续 L1/L3/L4 的 agent 如何拿到？建议放共享目录或 GitHub Release 资产，由用户决定。
2. **数据源偏离**：任务建议用 GSE92742 `fast_matrix.npy`，但该文件列顺序与 `col_sig_ids.csv` 不一致、且自身敲低信号弱；改用服务器已有的 LINCS2020 beta Level5（与参考表同源）。是否接受该偏离？
3. **化合物数 3155 vs 参考 3161**：用 Repurposing Hub 20200324 全表与 CMAP `trt_cp` 的 `cmap_name` 交集得到 3155 个；是否需要用另一个注释版本凑到 3161？
4. **EGFR hairpin 数 15 vs 参考 19**：取前 150 个样本时覆盖 15 个 hairpin（MTOR 18 与参考一致）；是否改为随机抽样或按 hairpin 分层抽样？
5. **KS 符号**：当前靶基因下调得到正 KS，与参考相反，属 L1 范围；L1 修复后 L3/L4 的参考值需按新符号重跑。

## 发现但未处理

1. **严重数据层问题**：`cmap_data/col_sig_ids.csv`（排序）与 `fast_matrix.npy`（GCTX COL 顺序）不一致。现有 `L5Provider` 用 `col_sig_ids.csv` 建 `sig_id → 列` 映射，会读到错误签名；服务器上 `~/LMNA/cache/_drug_median_matrix.npy` 也由该错误映射生成（与 beta 真值相关系数约 0）。本次未修改（超出 L0 范围），但 L1 的数据正确性修复必须先解决；建议单开任务统一改用 GCTX COL 顺序或生成正确的 `col_sig_ids.csv`。
2. **BH 实现**：`_benjamini_hochberg` 使用前向 `minimum.accumulate`，可出现 q < p（如 p=0.5 → q=0.04），不符合 BH 定义。测试只校验取值范围与单调性，未锁定错误行为；属 L1/L4 统计修复范围。
3. **KS 符号约定**：见上，属 L1。
4. **httpx 版本**：starlette 0.27 的 `TestClient` 依赖 `httpx.Client(app=...)`，httpx ≥0.28 已移除该参数；`requirements-dev.txt` 固定 `httpx>=0.24,<0.28`。
5. **FixtureProvider 的 cp sig_id**：为药物级中位数合成 `CP::<pert_iname>`，不是原始 LINCS sig_id；若后续任务需要原始 sig_id 需另行扩展。
6. `main.py` 的 health `provider` 字段直接返回环境变量字符串；若以后工厂做别名归一化，需要同步。

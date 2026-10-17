# task-L2 交付说明 · LMNA 缓存失效与版本化

任务ID / 分支 / 基线提交：**L2 / `fix/L2-cache-versioning` / `origin/main` @ `4697806`**（开工时为 L1 合并后的 `3b799ee`；提交前已 rebase 到含 L6/L4 的最新 main `4697806`）

## 改动文件（文件:行号范围）

| 文件 | 行号范围 | 内容 |
|---|---|---|
| `backend/config.py` | 43-48、89-102 | 新增 `ALGO_VERSION = "2"`；`signature_params()` 增加 `ALGO_VERSION` 与 L4 的 `DRUG_NULL_N` |
| `backend/cache_manager.py` | 1-258 | 缓存键哈希、版本化文件名、`atomic_write_json`、`read_json_file`、`exclusive_file_lock`、`clear_gene`/`list_cached_genes` 适配 |
| `backend/signature_engine.py` | 18-118 | 秩缓存文件名带 `ALGO_VERSION` + shRNA 列数；`fcntl.flock`（Windows 退 `msvcrt`）排他锁 + 双重检查；临时 memmap 原子替换 |
| `backend/drug_median_cache.py` | 1-131 | 药物中位数缓存同样版本化 + 文件锁 + 双重检查 + 临时文件原子替换 |
| `backend/task_queue.py` | 20、131-138、185-198、226、275、316-346、368 | 任务状态 JSON 全部原子写入/读取；药物缓存文件名带 `fast/normal` 模式；已与 L6 的去重/心跳/超时逻辑合并，无冲突残留 |
| `backend/tests/test_core_pure.py` | 142-156 | 适配秩缓存新路径（原测试覆盖 `_SHRNA_RANK_CACHE` 的写法在 L2 路径版本化后不再适用） |
| `backend/tests/test_L2_cache_versioning.py` | 1-294（新增） | L2 验收自动化测试 7 项 |

> 与 L6/L4 的关系：提交前已 rebase 到 `4697806`（L6、L4 均已合并）。`task_queue.py` 冲突按“保留 L6 的去重/心跳/超时逻辑 + L2 的原子写入与药物缓存 mode”解决；`config.py` 自动合并（`ALGO_VERSION` 与 `TASK_TIMEOUT_SEC`/`LMNA_ADMIN_TOKEN`/`DRUG_NULL_N` 等共存）。L4 的药物 p 值依赖 `DRUG_NULL_N`，已把它加入 `signature_params()` 缓存键，避免改 N 后仍读到旧 p 值。rebase 后全量测试 85 passed。

### 缓存命名

- 签名：`{GENE}_{h}_signature.json`
- 药物：`{GENE}_{h}_{method}_{mode}_drug_scores.json`（`mode` = `fast` / `normal`，由签名 `fast_mode` 决定）
- 其中 `h = sha1(json.dumps(signature_params(), sort_keys=True))[:10]`
- 秩缓存：`_shrna_rank_matrix.v{ALGO_VERSION}.{n_shrna}.dat` + 同名 `.shape.txt`
- 药物中位数：`_drug_median_matrix.v{ALGO_VERSION}.npy` + `_drug_names.v{ALGO_VERSION}.csv`

> 说明：药物缓存读取保留了“同哈希下按 mode 回退”的兼容逻辑。`GET /api/genes/{gene}/drugs` 只有 gene/method 两个参数，回退逻辑保证快速模式下写入的 `fast` 文件仍可被旧 API 读到（API 字段未增删改）。

## 测试

新增 `backend/tests/test_L2_cache_versioning.py`：

1. `test_signature_params_contains_algo_version` — 参数集合完整、版本为 `"2"`。
2. `test_ks_threshold_change_generates_new_cache_file` — 改 `KS_THRESHOLD` 后哈希变化、旧文件读不到、生成新文件、`list_cached_genes` 去重、`clear_gene` 删所有版本。
3. `test_drug_cache_filename_contains_hash_method_and_mode` — 药物文件名含哈希/method/mode，旧调用方式仍可读。
4. `test_concurrent_writes_never_produce_partial_json` — 2 个写线程合计 1000 次 `save_signature`，2 个读线程并发读取，断言无 `JSONDecodeError`。
5. `test_multiprocessing_rank_cache_built_once` — `multiprocessing`（spawn）起 2 个进程同时构建秩缓存，断言日志中“首次构建”只出现 1 次、最终文件形状/内容可读。
6. `test_drug_median_cache_versioned_and_built_once` — 药物中位数缓存带版本、第二次直接读缓存不重建。
7. `test_atomic_write_json_replaces_and_cleans_temp` — 原子写覆盖且无临时文件残留。

命令（cwd=`backend`）：

```bash
LMNA_FIXTURE_DIR=D:/agent-workspace/deliveries/task-L0/fixtures \
  D:/mine_Anaconda3/python.exe -m pytest -q
```

输出：

```
85 passed, 1 skipped, 5 warnings in 28.24s
```

（唯一 skip 为 `test_fixture_regression.py:132` 缺少 Table S1，原有 skip，与 L2 无关。完整日志：`D:\agent-workspace\deliveries\task-L2\pytest.log`）

## 验收逐条核对

- [x] **改变 `KS_THRESHOLD` 环境变量后再次计算，会生成新文件而不是读到旧文件。**
  `test_ks_threshold_change_generates_new_cache_file`：`signature_params_hash()` 随 `config.KS_THRESHOLD` 变化，旧哈希文件 `get_signature()` 返回 `None`，新文件路径不同且写入成功。
- [x] **两个线程同时 `save_signature`，读取方不会读到半截 JSON（1000 次循环写 + 并发读，不出现 `JSONDecodeError`）。**
  `test_concurrent_writes_never_produce_partial_json`：2 写线程 × 500 次 = 1000 次原子写；2 个读线程同时用 `json.load` 读取，未捕获任何 `JSONDecodeError`。临时文件名含 pid + 随机后缀，避免同一进程内两个线程写到同一个临时文件。
- [x] **用 `multiprocessing` 起 2 个进程同时构建秩缓存，最终文件可读且只构建一次（日志里“首次构建”只出现 1 次）。**
  `test_multiprocessing_rank_cache_built_once`：两进程经 `Barrier` 同时进入，断言 `log.count("首次构建 shRNA 排名矩阵") == 1`，并断言最终 `.dat`/`.shape.txt` 存在、shape 为 `978,8`、memmap 可读。

## 上线注意事项（必须执行）

> L1 + L2 一起上线。**部署时必须先停服务、删除旧 `cache/` 内容再启动**，否则旧秩缓存/药物中位数缓存会占用空间，且旧签名/药物 JSON 与新版本文件并存会造成清理混乱。服务器目录只读，以下步骤由人工执行。

```bash
# 1) 停服务（按现有部署方式）
# 2) 进入 LMNA 根目录
cd ~/LMNA

# 3) 删除旧缓存（保留 cache 目录本身）
rm -rf cache/signatures cache/drug_scores cache/tasks
rm -f  cache/_shrna_rank_matrix.dat cache/_shrna_rank_shape.txt
rm -f  cache/_shrna_rank_matrix*.lock cache/_drug_median_matrix*.lock
rm -f  cache/_drug_median_matrix.npy cache/_drug_names.csv

# 4) 确认（应只剩空目录/无缓存文件）
find cache -maxdepth 2 -type f

# 5) 启动服务后首次计算会重建：
#    - cache/_shrna_rank_matrix.v2.<n_shrna>.dat
#    - cache/_drug_median_matrix.v2.npy / _drug_names.v2.csv
#    - cache/signatures/<GENE>_<hash>_signature.json
#    - cache/drug_scores/<GENE>_<hash>_<method>_<mode>_drug_scores.json
```

补充：

- 以后每次修改签名/打分算法（含阈值语义、排序、符号约定等），必须把 `config.ALGO_VERSION` +1，旧缓存会自动失效（不会读到），但仍建议清理避免磁盘堆积。
- 药物缓存中的 `mode` 由签名的 `fast_mode` 决定；生产 `FAST_MODE_TOP_N=0` 时均为 `normal`。
- L1 遗留事项仍成立：`~/LMNA/cache/_drug_median_matrix.npy` 需由 **L8** 修复列序后重建；L2 改为版本化文件名，不会再误读旧文件，但数据正确性仍以 L8 为准。

## 待人工确认（🧑‍⚖️）

1. **`mode` 取值**：任务原文只写 `{mode}`，本实现按签名是否走快速模式取 `fast`/`normal`。如原意是其他维度（如 paper/default 阈值模式），需要给出取值规则；当前 FDR/阈值已在哈希中，不影响失效。
2. **`ALGO_VERSION` 初始值**：按任务原文设为 `"2"`。L1 是首次带版本上线，是否希望从 `"2"` 开始（而非 `"1"`）请确认。
3. **Windows 文件锁回退**：生产 Linux 使用 `fcntl.flock`（任务要求）；本地 Windows 测试自动回退到 `msvcrt.locking`。若生产环境不是 Linux，请告知。

## 发现但未处理

1. `DELETE /api/cache/{gene}` 仍无认证（任务文件明确转 L6）。
2. 任务状态更新是“读-改-写”，原子写只保证不出现半截 JSON，不保证两个进程同时更新同一任务时无丢失更新（当前同一 task_id 仅 worker 更新，风险低）。
3. `_drug_median_matrix` 列序问题仍由 L8 负责（L0/L1 已记录），L2 不改变统计语义。
4. `backend/tests/test_core_pure.py` 的秩缓存测试做了最小适配（改为覆盖 `CACHE_DIR`），未改动 L1 统计断言。

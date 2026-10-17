# task-L6 交付说明 · LMNA 工程加固

- 任务 ID：L6
- 分支：`fix/L6-hardening`
- 基线提交：`3b799ee`（origin/main，含 L1 合并提交）
- 运行目录：`backend/`（裸 import）

## 改动文件

| 文件 | 行号 | 内容 |
|---|---|---|
| `backend/config.py` | 71-78 | 新增 `TASK_TIMEOUT_SEC`（默认 7200）、`LMNA_ADMIN_TOKEN`、`LMNA_CORS_ORIGINS` |
| `backend/task_queue.py` | 28-85 | 超时判定、去重标识（gene/method/mode/参数哈希）、提交锁 |
| `backend/task_queue.py` | 124-135 | worker 每个阶段更新 `updated_at`（签名完成、开始筛药、筛药完成） |
| `backend/task_queue.py` | 211-248 | `_find_active_task`：仅命中 pending/running；顺带把超时 running 标 failed |
| `backend/task_queue.py` | 250-330 | `submit`/`submit_ex` 去重；`get_status` 心跳超时 → failed |
| `backend/task_queue.py` | 338-366 | `mark_stale_tasks_on_startup`：启动时 pending/running → failed |
| `backend/main.py` | 33-58 | CORS 改为 `LMNA_CORS_ORIGINS`（逗号分隔），为空不加中间件（D2） |
| `backend/main.py` | 65-68 | FastAPI 启动事件调用残留任务清理 |
| `backend/main.py` | 144-153 | 计算接口改用 `submit_ex`，响应新增 `deduplicated` 字段；`status` 返回实际状态 |
| `backend/main.py` | 218-241 | `DELETE /api/cache/{gene}` 校验 `X-Admin-Token`；未设置 `LMNA_ADMIN_TOKEN` 一律 403 |
| `backend/provider_factory.py` | 30-39 | `create_provider("l3")` 立即抛出清楚的 NotImplementedError |

API 兼容性：仅新增字段 `deduplicated` 和任务 JSON 的 `mode`/`params_hash`/`dedup_key`，未改名、未删除既有字段；`status` 字段仍存在。

## 测试

新增：
- `backend/tests/test_task_hardening.py`（去重、并发去重、参数变化、超时、启动清理）
- `backend/tests/test_api_hardening.py`（接口层 3 次 POST 去重、DELETE 鉴权、CORS 解析）
- `backend/tests/test_provider_l3.py`（L3 创建/启动失败）

运行命令（cwd=`backend`）：

```bash
LMNA_FIXTURE_DIR='D:\agent-workspace\deliveries\task-L0\fixtures' \
  D:\mine_Anaconda3\python.exe -m pytest -q
```

输出：

```
.....................................s...............................    [100%]
68 passed, 1 skipped, 5 warnings in 14.06s
```

跳过项为仓库原有的夹具相关可选测试（与本次改动无关）。完整日志：`D:\agent-workspace\deliveries\task-L6\pytest.log`。

## 验收逐条核对

- [x] 连续提交 3 次同一基因只产生 1 个计算（task_id 相同）
  - 单元：`test_three_submits_same_gene_share_one_task`（worker 仅调用 1 次、仅 1 个任务文件）
  - 接口：`test_api_three_compute_requests_share_one_task`（3 次 POST 返回同一 task_id，`deduplicated` 依次为 False/True/True）
  - 并发：`test_concurrent_submits_create_only_one_task`（8 线程同时提交仍只 1 个任务）
- [x] running 且 `updated_at` 为 3 小时前 → `GET /api/tasks/{id}` 返回 failed
  - `test_get_status_marks_three_hour_old_running_as_failed`（message 含“超时”）
- [x] 不带 token 调 `DELETE /api/cache/CDK4` 返回 403
  - `test_delete_cache_without_token_returns_403`；未配置 token 时即使带 header 也 403；正确 token 返回 200

## 待人工确认（🧑‍⚖️）

- D2 CORS 白名单实际取值：代码已实现为 `LMNA_CORS_ORIGINS` 逗号分隔；同源 nginx 反代部署可留空（不启用中间件）。上线前请确认是否需要填写来源。
- `LMNA_ADMIN_TOKEN` 需在上线环境显式设置，否则 DELETE 缓存接口保持禁用（403）。建议用强随机值，并只发给运维。

## 发现但未处理

- 去重锁是**进程内**的（`threading.Lock`）。按 D6 `gunicorn -w 1 --threads 8` 部署可完全覆盖；若将来改成多 worker 进程，需要文件锁或数据库唯一约束。
- 旧版本创建的任务 JSON 没有 `dedup_key`，不会参与去重（滚动升级窗口内可能重复）。新任务不受影响。
- pending 任务没有超时（任务要求只对 running 做心跳超时）；启动清理负责回收重启前的 pending。
- 前端进度条/轮询属 L5/L7f 范围，本次未改动。
- `@app.on_event("startup")` 在 FastAPI 0.100 有弃用提示，但保持与该版本兼容；后续升级可改 lifespan。
- `provider_factory.py` 仍保留 `L3Provider` import 以便后续实现时直接接回，当前不会实例化。

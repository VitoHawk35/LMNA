# L7f · 任务系统（SQLite 任务表 + 独立 worker 进程）（设计文档）

- 状态：方案待人工确认（只出文档，未实施）
- 基线：LMNA `main` @ `315f965`
- 关联：报告任务三·1 的统一系统架构；L7a（共享数据层）；L7d（上传签名需要 owner 概念）；L2（缓存版本）

## 1. 结论摘要

当前任务系统是“JSON 文件 + API 进程内的 `ProcessPoolExecutor`”：

- 每个任务一个 `cache/tasks/<id>.json`，状态更新是读-改-写，无锁、无事务；
- worker 池由 API 进程创建（`backend/task_queue.py:28-33`），`max_workers=2`；
- API 重启/崩溃会丢任务；没有重试、没有心跳、没有幂等、没有取消；
- `all_scores`（19,811 项）随结果写进 JSON，单任务文件可达 MB 级；
- `TaskQueue.submit` 直接把任务丢进进程池，进程池的 future 不持久化，重启即丢。

目标架构（与报告任务三一致）：

```
React 前端
   │ /api/*
Nginx（TLS/静态）
   │
FastAPI 单体（auth · signatures · screen · genes · jobs）
   ├── SQLite/Postgres（用户·签名·任务·结果索引）
   ├── 任务队列（SQLite jobs 表；后期可换 Redis/Arq）
   └── Compute Worker ×N（独立进程）
          └── 共享 L1000 数据层（L7a memmap / drug_median / ref_ncs / metadata）
```

本方案只替换“任务持久化 + 执行”这一层，保持现有 HTTP 契约（提交/查询/列表）不变；结果大字段从 JSON 移到独立结果文件，DB 只存索引和 top/bottom。

推荐 SQLite 作为第一阶段（单机、零运维、WAL 足够支撑当前并发）；通过 `JobStore` 抽象为后续 Postgres/Redis 留接口。

## 2. 现状与证据

### 2.1 代码事实

- `backend/task_queue.py:28-33`：全局 `ProcessPoolExecutor(max_workers=2)`，懒加载在 API 进程内。
- `backend/task_queue.py:144-176`：`submit` 生成 16 位 UUID，写初始 JSON，再 `executor.submit(...)`；future 没有保存，无法查询/取消。
- `backend/task_queue.py:109-133`：`_update_task_status` 每次读整个 JSON、改字段、重写；并发更新会互相覆盖。
- `backend/task_queue.py:178-197`：`get_status` / `list_tasks` 直接读文件；`list_tasks` 按 mtime 排序，全目录扫描。
- `backend/task_queue.py:43-106`：worker 在子进程里构造 `CacheManager`、`L5Provider`、`SignatureEngine`、`DrugScorer`；`L5Provider` 在每个进程首次使用时构建 memmap 和元数据。
- `backend/main.py:93-114`：`POST /api/genes/{gene}/compute` 提交任务；`GET /api/tasks/{id}`、`GET /api/tasks` 查询。
- `backend/main.py:152-173`：`/drugs` 从缓存 JSON 读取，`all_scores` 已在缓存里但响应只返回 top/bottom。
- `.gitignore:1`：`cache/` 不入库；任务 JSON 属于运行时数据。

### 2.2 现有行为的问题

| 问题 | 触发条件 | 后果 |
|---|---|---|
| API 重启丢任务 | 部署/崩溃 | 已提交任务永远 pending |
| 进程池不持久化 | 同上 | 无法恢复/重试 |
| JSON 读-改-写竞争 | 多请求/多 worker | 状态回退、字段丢失 |
| 无心跳/超时 | worker 卡死 | 任务永远 running |
| 无幂等 | 用户重复点击 | 重复计算、缓存竞争 |
| 无取消 | 用户改主意 | 无法停止长任务 |
| `all_scores` 进 JSON | 每次结果 | 文件膨胀、序列化慢 |
| 全目录扫描 | 任务多 | 列表接口变慢 |

## 3. 目标与非目标

### 3.1 目标

- 任务状态持久化、原子更新、重启可恢复。
- 独立 worker 进程，可水平扩展（同一台机器多进程）；API 不执行重计算。
- 至少一次执行 + 幂等键，避免重复任务。
- 心跳/超时/重试/取消。
- 结果与任务索引分离；`all_scores` 不再写 JSON。
- HTTP API 兼容现有字段；旧 JSON 任务可迁移/回退。

### 3.2 非目标

- 不在本任务中引入 Redis/Celery/Arq（后期可选）。
- 不实现用户认证/配额（L7d/后续任务）；但 schema 预留 `owner_id`。
- 不做分布式多机调度。
- 不在本任务中写代码。

## 4. 数据库设计（SQLite）

### 4.1 连接参数

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
```

- 单写多读；worker claim 使用 `BEGIN IMMEDIATE` 短事务。
- 数据库文件：`<DATA_DIR>/lmna.db`（不入 git；与 `cache/` 同级的运行时目录）。
- 备份：WAL checkpoint + 文件拷贝；或 `sqlite3 .backup`。

### 4.2 表结构

```sql
CREATE TABLE schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);

CREATE TABLE jobs (
    id                TEXT PRIMARY KEY,           -- uuid4 hex（保持 16/32 位）
    kind              TEXT NOT NULL,              -- compute_signature | score_drugs | ...
    status            TEXT NOT NULL,              -- queued|running|completed|failed|cancelled
    gene              TEXT,
    method            TEXT,
    mode              TEXT,                       -- lof|gof
    source            TEXT,                       -- shrna|oe|xpr|user_deg
    params_json       TEXT NOT NULL DEFAULT '{}',
    priority          INTEGER NOT NULL DEFAULT 100,
    idempotency_key   TEXT UNIQUE,
    attempts          INTEGER NOT NULL DEFAULT 0,
    max_attempts      INTEGER NOT NULL DEFAULT 3,
    worker_id         TEXT,
    progress          REAL NOT NULL DEFAULT 0,
    message           TEXT,
    result_path       TEXT,                       -- cache/results/<id>.npz
    result_json       TEXT,                       -- 小结果/top-bottom 摘要
    error             TEXT,
    cancel_requested  INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,              -- ISO8601 UTC
    started_at        TEXT,
    finished_at       TEXT,
    heartbeat_at      TEXT,
    owner_id          TEXT
);

CREATE INDEX idx_jobs_queue ON jobs(status, priority, created_at);
CREATE INDEX idx_jobs_owner ON jobs(owner_id, created_at);
CREATE INDEX idx_jobs_heartbeat ON jobs(status, heartbeat_at);

CREATE TABLE job_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    at         TEXT NOT NULL,
    event      TEXT NOT NULL,                     -- queued|claimed|progress|completed|failed|retry|cancelled
    detail     TEXT
);

CREATE TABLE signatures (
    signature_id TEXT PRIMARY KEY,
    gene         TEXT,
    mode         TEXT,
    source       TEXT,
    payload_path TEXT,                            -- JSON/JSON.gz
    qc_json      TEXT,
    created_at   TEXT NOT NULL,
    owner_id     TEXT
);
```

说明：

- `status` 用 CHECK 约束（SQLite 支持）限制枚举。
- `params_json` 保存方法参数/阈值/数据版本，便于复现；不要把大数组放进去。
- `idempotency_key` 建议 = `sha256(kind|gene|method|mode|source|data_version|params_hash)`；同一键在 `queued/running/completed` 时直接返回已有 job id（`completed` 是否复用由调用方决定，默认复用）。
- `heartbeat_at` 由 worker 每 10–15 s 更新；reaper 判定超时（默认 120 s）。
- `result_path` 指向 `cache/results/<job_id>.npz`；`result_json` 只放 top/bottom（各 50 条）和摘要。

### 4.3 结果文件

```
<cache>/results/<job_id>.npz
  drug_names  (n_drugs,)  <U...
  scores      (n_drugs,)  float32
  top_idx     (k,)        int32
  bottom_idx  (k,)        int32
  meta        JSON string
```

- 19,811 个 float32 = 79 KB；NPZ 压缩后通常更小。
- API 的 `all_scores` 若仍要返回，可从 `.npz` 流式读取；默认只返回 top/bottom（与当前 `/drugs` 行为一致）。
- 保留策略：`completed` 结果默认 90 天；`failed/cancelled` 30 天；由清理任务执行。

## 5. Worker 设计

### 5.1 进程模型

- 独立入口：`python -m backend.worker`（或 `python backend/worker.py`），不依赖 FastAPI 进程。
- 每个 worker 进程：
  1. 打开 DB，设置 WAL/busy_timeout；
  2. 构造一次 `L5Provider` / `LandmarkStore`（进程内复用，避免每任务重建）；
  3. 循环 claim → 执行 → 写结果 → 更新状态；
  4. 捕获 SIGTERM/SIGINT：停止 claim，等待当前任务完成或超时后退出；
  5. 心跳线程每 10–15 s 更新当前 job 的 `heartbeat_at`。
- 并发：`LMNA_WORKERS=N`（默认 1–2）；SQLite 写入串行，但 claim 事务很短，计算在事务外。
- 内存：每个 worker 映射 L7a 1.85 GB（页缓存共享）+ 任务工作集；`N=2` 在 8 GB 机器上也可运行（页缓存共享）。

### 5.2 Claim 伪代码

```python
def claim(conn, worker_id):
    with conn:  # BEGIN IMMEDIATE
        row = conn.execute("""
            SELECT id FROM jobs
            WHERE status='queued'
            ORDER BY priority ASC, created_at ASC
            LIMIT 1
        """).fetchone()
        if not row:
            return None
        conn.execute("""
            UPDATE jobs
            SET status='running', worker_id=?, started_at=?,
                heartbeat_at=?, attempts=attempts+1
            WHERE id=? AND status='queued'
        """, (worker_id, now(), now(), row["id"]))
        return row["id"]
```

- 必须有 `WHERE status='queued'` 防止重复 claim。
- `BEGIN IMMEDIATE` 获取写锁；不要在网络/计算期间持有事务。

### 5.3 执行与状态

```python
def run_job(job):
    update(progress=0, message="开始")
    if job.cancel_requested:
        finish("cancelled"); return
    try:
        result = compute(job)              # 复用现有 SignatureEngine/DrugScorer
        save_result_npz(job.id, result)    # 原子写：tmp + rename
        update(status="completed", progress=1, result_path=..., result_json=top_bottom)
    except Exception as e:
        if job.attempts < job.max_attempts:
            update(status="queued", error=str(e), message="重试")
        else:
            update(status="failed", error=traceback)
```

- 进度：`SignatureEngine` 的 bootstrap 循环可回调 `progress`（可选）；至少更新 `message`。
- 取消：API 只置 `cancel_requested=1`；worker 在阶段边界检查；运行中的 numpy 计算不能强杀，必要时由 reaper 超时处理。
- 重试：默认 3 次；失败原因写 `error`；不重试参数错误（4xx 类）。

### 5.4 Reaper（可由 worker 或独立 cron 执行）

```sql
-- 心跳超时的 running -> queued（attempts 已计）
UPDATE jobs
SET status='queued', worker_id=NULL, message='心跳超时，重新排队'
WHERE status='running'
  AND heartbeat_at < datetime('now', '-120 seconds')
  AND attempts < max_attempts;
-- 超过重试上限 -> failed
UPDATE jobs
SET status='failed', finished_at=datetime('now'),
    error='心跳超时且超过最大重试次数'
WHERE status='running'
  AND heartbeat_at < datetime('now', '-120 seconds')
  AND attempts >= max_attempts;
```

- reaper 每 30–60 s 跑一次；与 worker 同一进程或独立 `python -m backend.reaper`。
- 注意：如果任务确实需要 >120 s，worker 心跳线程必须持续更新；不要用固定任务超时。

## 6. API 设计（保持兼容）

### 6.1 现有契约

| 方法 | 路径 | 变化 |
|---|---|---|
| POST | `/api/genes/{gene}/compute` | 内部改为 `JobStore.submit`；响应字段不变（`task_id/gene_name/method/status`）；新增可选 `idempotency_key` |
| GET | `/api/tasks/{task_id}` | 从 DB 读；响应字段兼容（`task_id/gene_name/method/status/created_at/updated_at/message/result/error`） |
| GET | `/api/tasks` | 从 DB 分页；新增 `limit/offset/status` 查询参数（只加） |
| GET | `/api/genes/{gene}/drugs` | 从结果文件读；响应不变 |

### 6.2 新增（可选）

- `POST /api/tasks/{task_id}/cancel`：置 `cancel_requested=1`；返回当前状态。
- `GET /api/tasks/{task_id}/events`：审计事件。
- `POST /api/tasks/{task_id}/retry`：仅 `failed/cancelled` 可重试；创建新 job 或重置 attempts（建议新建，保留历史）。
- 所有新字段写入 pydantic 模型并给默认值；不删不改现有字段名。

### 6.3 响应映射

```json
{
  "task_id": "...",
  "gene_name": "LMNA",
  "method": "xsum",
  "status": "completed",
  "created_at": "...",
  "updated_at": "...",
  "message": "计算完成",
  "result": { "signature": {...}, "drug_results": {...} },
  "error": null
}
```

- `updated_at` 映射 `COALESCE(finished_at, heartbeat_at, started_at, created_at)`。
- `result` 由 `result_json` + 结果文件组装；大字段按需返回。

## 7. 与报告任务三架构的对齐

| 报告组件 | 本方案 | 说明 |
|---|---|---|
| React 统一前端 | 不变 | 现有 `frontend/index.html` 可先继续用 |
| Nginx（TLS/静态） | 不变 | 部署层 |
| FastAPI 单体（auth/signatures/screen/genes/jobs） | 保留；jobs 改为 DB | 后续可加 auth/signatures 路由 |
| SQLite/Postgres（用户·签名·任务·结果） | SQLite `jobs/signatures/job_events` | `owner_id` 预留；Postgres 通过 `JobStore` 适配 |
| 任务队列（SQLite 表 → Redis/Arq） | `jobs` 表 + 轮询 | `JobStore` 接口隔离，后期换 Redis 不改 API |
| Compute Worker ×N | 独立 `backend.worker` | 复用 `SignatureEngine/DrugScorer` |
| 共享 L1000 数据层 | L7a + L7b | worker 只读映射 |

`JobStore` 接口（建议）：

```python
class JobStore(ABC):
    def submit(self, kind, params, idempotency_key=None, owner_id=None) -> str: ...
    def get(self, job_id) -> dict | None: ...
    def list(self, limit, offset, status=None, owner_id=None) -> list: ...
    def cancel(self, job_id) -> bool: ...
    def claim(self, worker_id) -> dict | None: ...
    def heartbeat(self, job_id, progress=None, message=None) -> None: ...
    def complete(self, job_id, result_path, result_json) -> None: ...
    def fail(self, job_id, error, retryable) -> None: ...
```

- SQLite 实现 `SQLiteJobStore`；后期 `RedisJobStore` 只实现同一接口。
- API 与 worker 都依赖接口，不直接写 SQL。

## 8. 迁移步骤

### 8.1 从 JSON 迁移

1. 新增 `schema_migrations`，创建表（幂等）。
2. 写一次性迁移脚本：
   - 扫描 `cache/tasks/*.json`；
   - 为每个文件插入 `jobs` 行（保留原 `task_id`、时间、status；`queued/running` 统一改为 `queued` 并 `attempts=0`）；
   - 原 JSON 中的 `result` 若包含 `all_scores`，写入 `cache/results/<id>.npz`，DB 只存 top/bottom；
   - 迁移后保留原 JSON 30 天（只读），用于回滚/核对。
3. 启动新 worker，再切 API 读写 DB。
4. 双读期：API 先查 DB，未命中再查旧 JSON（兼容未迁移/回滚）；30 天后移除。

### 8.2 部署顺序

```
1) 备份 cache/tasks/*.json 与 lmna.db（若已存在）
2) 运行迁移脚本（可重复执行，幂等）
3) 启动 N 个 worker（先不接流量）
4) 启动/重启 API，切 JobStore=sqlite
5) 冒烟：提交 3 个任务（新基因/缓存命中/失败参数），检查状态、结果、取消
6) 观察 1 天；确认无 pending 丢失后，停止旧 JSON 写入
```

### 8.3 回滚

- 环境变量 `LMNA_TASK_BACKEND=json|sqlite`；回滚只需切回 `json` 并重启 API。
- 旧 JSON 保留 30 天；DB 不删除。
- 注意：回滚期间新提交的 DB 任务不会被旧系统执行；回滚前先排空队列。

## 9. 测试与验收

### 9.1 自动测试

- [ ] 提交 100 个任务，全部最终 `completed/failed`，无重复执行（用计数器）。
- [ ] 相同 `idempotency_key` 提交两次，返回同一 `task_id`。
- [ ] worker 在执行中被 `kill -9`，重启后 reaper 将任务重新排队；`attempts` 增加。
- [ ] 心跳正常的长任务不会被 reaper 误杀。
- [ ] 取消：`queued` 任务立即变 `cancelled`；`running` 任务在阶段边界停止。
- [ ] 失败重试 3 次后变 `failed`，`error` 有堆栈。
- [ ] API 兼容：旧字段齐全，`/api/tasks` 分页正确。
- [ ] 迁移脚本：10 个 JSON（含 completed/failed/running）迁移后字段一致。
- [ ] `all_scores` 不再写入 DB；结果文件可读、可删除。
- [ ] 并发 4 个 worker 不重复 claim（SQLite `BEGIN IMMEDIATE`）。
- [ ] 备份/恢复演练：从 DB 备份 + 结果文件恢复后，任务可查询。

### 9.2 手工验收

- [ ] 重启 API 不影响运行中的 worker。
- [ ] 重启 worker 不影响 API 查询。
- [ ] `/api/health` 增加队列深度/worker 数（可选）。
- [ ] 任务列表在 10,000 条记录下 <200 ms（索引生效）。

## 10. 工作量估算

| 工作 | 人日 |
|---|---|
| Schema + `SQLiteJobStore` + 迁移脚本 | 1.0 |
| Worker 进程（claim/heartbeat/reaper/信号） | 1.0 |
| API 适配 + 兼容层 + 测试 | 1.0 |
| 结果文件/`all_scores` 拆分 | 0.5 |
| 并发/崩溃/取消/幂等测试 | 1.0 |
| 部署/运维文档/回滚演练 | 0.5 |
| **合计** | **5.0 人日** |

可选：Redis/Arq 适配 +2 人日；auth/owner 隔离 +2 人日（与 L7d 上传一起）。

## 11. 待人工确认

1. 第一阶段用 SQLite 还是直接上 Postgres？单机研究系统建议 SQLite；若未来多机/多用户，直接 Postgres 可省一次迁移。
2. worker 并发数默认 1 还是 2？受内存与 CPU 影响；建议默认 1，压测后调。
3. 结果保留期（90 天）与磁盘配额是否接受？
4. 回滚期 30 天是否足够？
5. 是否现在就引入 `owner_id`/认证，还是等 L7d 上传功能一起做？
6. 是否允许在部署窗口短暂停止 API（迁移最简单），还是要求零停机双写？

# LMNA 后端现状说明（Backend Situation）

> 文档性质：长期维护用的“现状说明书”，不是设计提案，也不是部署手册的替代品。
> 适用代码：GitHub `main` @ `1850826`（2026-10-18；基线 `8d367b6` 已含 L0–L4/L6/L8/L2，随后合并 L5 `4517e43` 与本文档 `1850826`）。正文中标注 `8d367b6` 的行号均以该基线核对；L5 之后仅前端/文档变化，后端行号不受影响。
> 现网对象：老实例 `~/lmna_app/LMNA`（v1）与新实例 `~/lmna_v2`（v2）。
> 最后核对：2026-10-18，代码为工作区 `D:\agent-workspace\worktrees\task-DOC`；服务器为 `keji@10.39.15.238`，全程只读（未改代码、未删缓存、未重启服务）。
> 维护规则：任何改变 API 字段、缓存文件名、统计口径、部署端口或启动方式的提交，都必须同步更新本文对应章节；纯重构也必须更新“模块清单”和“修复历史”。

## 0. 证据标记与阅读方式

本文对事实来源做四级标记，避免把推断当成实测：

| 标记 | 含义 |
|---|---|
| 【代码】 | 已逐行阅读仓库或服务器上的代码确认，给出 `文件:行号` |
| 【实测】 | 在服务器上只读探测/读取确认（HTTP、文件、日志、numpy/h5py 只读加载） |
| 【日志/报告】 | 来自 `deliveries/deploy/部署完成报告-2026-10-18.md`、`server_v2.log`、`zsvc_build.log` 等 |
| 【推断】 | 只从 v1 代码或数据结构推断，未做端到端实测；使用时需复核 |

重要原则：

1. 以代码为准，不以旧交付说明为准。旧交付说明里的行号是当时的基线，合并后可能漂移；本文行号按 `8d367b6` 重新核对（L5 合并只改前端与文案，不影响后端行号）。
2. v1 是**独立代码线**，不在 GitHub 仓库里；不能用 GitHub `main` 的行为去描述 v1。
3. 服务器上的数据副本有两份：共享 `~/cmap/cmap_data` 与 v2 专用 `~/cmap_v2_data`。两者只有 CSV 不同，矩阵/GCTX 是软链接。不要把“v2 已修复”误写成“共享数据已修复”。

---

## 1. 版本与部署拓扑

### 1.1 三条代码线

| 代码线 | 位置 | 基线/版本 | 用途 | 与 GitHub 的关系 |
|---|---|---|---|---|
| GitHub 主线 | `origin/main` | `1850826`（基线 `8d367b6` + L5 + 本文档） | 后续开发、v2 部署 | 唯一权威仓库 |
| v1 现网 | `~/lmna_app/LMNA`（服务器） | 无 git 版本信息；含 `l4zsvc`/FDA/export/figure3 | 老服务，继续对外 | **不在仓库内**，是历史分支 |
| v2 新实例 | `~/lmna_v2`（服务器） | `8d367b6` | 新端口验证 | 后端 13 个 `.py` 与 `8d367b6` 的 md5 **逐文件完全一致**【实测】 |

v2 后端一致性核对（2026-10-18，md5 全部相同）：

```text
provider_factory.py     0b1759a92d94107fc1ebaf513bff2e96
suitability.py          2514518c0e286bf7e402d52f1d816641
drug_median_cache.py    2e571ffc67343b1ecfa19611091c8eaa
cache_manager.py        32c70379edd1fcfa4bd22cf963544871
main.py                 34d7953c0839aa8116692e4722f8f488
data_provider.py        3b64130d224700c6c5edbf642fefa991
signature_engine.py     517e8980888e3aaee39865824fb67c1d
l5_provider.py          8b83f87a5febf473da0cf2dcc261e8b8
l3_provider.py          c3ebc5c6c37378ef0366f5729b50b4dd
fixture_provider.py     da56bfa761577b97427015570b91eda0
drug_scorer.py          e509f916547a6436b9cd8c0eff423647
config.py               f30945322866913c74ecf899444a3d42
task_queue.py           f526696286644e38010ec7275a8884d3
```

只有 v2 前端被部署时改过一行：仓库 `frontend/index.html:165` 是 `const API_BASE = 'http://localhost:8001';`，服务器 v2 上改成 `https://10.39.15.238:8004`【实测】。因此：

- 不要把服务器上的 v2 前端当成仓库内容；
- 正式前端任务（L5）已于 2026-10-18 完成并合并（`6812e33` → 合并提交 `4517e43`）；仓库 `main` 现为 `1850826`（含 L5 与本文档）。服务器 v2 前端仍是部署时的旧版（`API_BASE` 硬编码），需另行部署才会生效。

### 1.2 端口与访问地址

| 实例 | API | 前端 | 协议 | 说明 |
|---|---|---|---|---|
| LMNA v1 | `https://10.39.15.238:8003` | `https://10.39.15.238:8083` | HTTPS（自签） | 老服务；API 由 `python3 main.py` 启动，前端由 Python `http.server` 启动 |
| LMNA v2 | `https://10.39.15.238:8004` | `https://10.39.15.238:8084` | HTTPS（自签） | 新实例；uvicorn + 独立静态服务 |
| cmap（老） | `10.39.15.238:8001` | `10.39.15.238:8081` | 未在本次核对 | 与 LMNA 共用 `~/cmap/cmap_data` |
| cmap_v2 | `10.39.15.238:8007` | 同端口 | 未在本次核对 | 使用 `~/cmap_v2_data` |

自签证书的浏览器提示与老服务一致；本文不复制、不引用任何证书/私钥内容。

### 1.3 目录、数据、缓存

| 用途 | v1 | v2 |
|---|---|---|
| 代码 | `/home/keji/lmna_app/LMNA` | `/home/keji/lmna_v2` |
| 数据目录 | `~/lmna_app/cmap_data`（小，主要是元数据）；生产 shRNA/drug 实际读 `/data2/wanggang/camp/level3`、`/data2/wanggang/camp/level4` | `/home/keji/cmap_v2_data`（矩阵/GCTX 软链接到 `~/cmap/cmap_data`，两个 CSV 是本地修正副本） |
| 缓存 | `~/lmna_app/LMNA/cache` | `/home/keji/lmna_v2_cache` |
| 数据库 | 无 | 无（JSON 文件任务队列） |
| 管理令牌 | 无 | `~/lmna_v2/.admin_token`（部署脚本读取，权限 600；本文不记录内容） |

v2 数据目录的实际形态【实测】：

```text
/home/keji/cmap_v2_data/
├── col_sig_ids.csv                 17,433,427 B  （修正后，473,647 行 + 表头）
├── col_sig_ids.csv.bak-20261018-014410  17,907,075 B（旧字典序）
├── row_gene_ids.csv                67,518 B      （修正后，12,328 行 + 表头）
├── row_gene_ids.csv.bak-20261018-014410   79,847 B（旧 gene_info 顺序）
├── fast_matrix.npy -> /home/keji/cmap/cmap_data/fast_matrix.npy
├── GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx -> 同共享目录
├── GSE92742_Broad_LINCS_gene_info.txt.gz -> 同共享目录
├── GSE92742_Broad_LINCS_sig_info.txt.gz -> 同共享目录
├── GSE92742_Broad_LINCS_pert_info.txt.gz -> 同共享目录
└── GSE92742_Broad_LINCS_cell_info.txt.gz -> 同共享目录
```

共享 `~/cmap/cmap_data` 的 CSV **仍是旧文件**【实测】：

```text
col_sig_ids.csv  md5 a55b1e318fb1267ef5c7e35efeac7c49  首行 AML001_CD34_24H:A05（字典序）
row_gene_ids.csv md5 1365df63dd2decb0161cef5925a9ee07  首行 780（gene_info 顺序）
```

v2 修正副本【实测】：

```text
col_sig_ids.csv  md5 b7d0b45df6ad1db07b519103b2641984  首行 CPC005_A375_6H:BRD-A85280935-003-01-7:10
row_gene_ids.csv md5 4aa1c61af86dc224e59b0228f046b2d6  首行 5720
```

### 1.4 进程、PID、日志

v1【实测】【代码】：

| 项 | 值 |
|---|---|
| API 启动 | `bash ~/lmna_app/LMNA/start_server.sh start`，内部 `cd backend && conda activate cmap && nohup python3 main.py >> server.log 2>&1 &` |
| API PID | `~/lmna_app/LMNA/cache/lmna_server.pid` |
| API 日志 | `~/lmna_app/LMNA/backend/server.log` |
| 前端启动 | `bash ~/lmna_app/LMNA/start.sh`，内部 Python `http.server` + `ssl.wrap_socket`，端口 8083 |
| 前端 PID | `~/lmna_app/LMNA/cache/lmna_frontend.pid` |
| 前端日志 | `~/lmna_app/LMNA/frontend/server.log` |
| 状态检查 | `bash ~/lmna_app/LMNA/status.sh` |
| 开机自启 | `portal-stack.service`（oneshot）→ `~/portal/restart_all.sh` → 若 8003 未监听则 `bash ~/lmna_app/LMNA/start.sh` |

v1 进程当前形态【实测】：主进程 `python3 main.py`（PID 2916474），两个 ProcessPoolExecutor 子进程（2917856/2917857），前端 PID 2916476；8003/8083 均在监听。

v2【实测】【代码】：

| 项 | 值 |
|---|---|
| API 启动 | `bash ~/lmna_v2/start_v2.sh` |
| API PID | `~/lmna_v2/.lmna_v2.pid` |
| API 日志 | `~/lmna_v2/server_v2.log` |
| 前端启动 | `bash ~/lmna_v2/start_frontend_v2.sh`（`serve_frontend_v2.py`，端口 8084） |
| 前端 PID | `~/lmna_v2/.lmna_frontend_v2.pid` |
| 前端日志 | `~/lmna_v2/frontend_v2.log` |
| 一键启动 | `bash ~/start_new_instances.sh`（还会拉起 cmap_v2 等非 LMNA 服务；只需 LMNA 时用上面的单独命令） |
| 一键停止 | `bash ~/stop_new_instances.sh`（会停止所有新实例；只停 LMNA 用 `stop_frontend_v2.sh` + `stop_v2.sh`） |
| 开机自启 | **没有** systemd 单元；重启服务器后必须手工执行启动脚本【实测】 |

v2 进程当前形态【实测】：uvicorn 主进程 2797792，ProcessPool worker 子进程 2799377/2799378，前端 2797795；8004/8084 均在监听。

### 1.5 启动 / 停止命令（可直接复制）

> 以下命令来自部署完成报告第 6 节，并于 2026-10-18 在服务器上核对过脚本内容【日志/报告】【实测】。

v2 一键：

```bash
ssh -i ~/.ssh/lmna_deploy keji@10.39.15.238
bash ~/start_new_instances.sh
bash ~/stop_new_instances.sh
```

v2 单独：

```bash
bash ~/lmna_v2/start_v2.sh
bash ~/lmna_v2/start_frontend_v2.sh
bash ~/lmna_v2/stop_v2.sh
bash ~/lmna_v2/stop_frontend_v2.sh
```

v1 单独：

```bash
bash ~/lmna_app/LMNA/start.sh
bash ~/lmna_app/LMNA/status.sh
bash ~/lmna_app/LMNA/stop.sh
# 只操作 API：
bash ~/lmna_app/LMNA/start_server.sh start
bash ~/lmna_app/LMNA/start_server.sh status
bash ~/lmna_app/LMNA/start_server.sh stop
```

v1 `start_server.sh` 的固定参数【实测】：

```bash
export DATA_PROVIDER=l4zsvc
export BOOTSTRAP_N=100000
export FDR_THRESHOLD=0.001
export KS_THRESHOLD=0.2
export FAST_MODE_TOP_N=0
export DRUG_PERM_N=10000
export API_PORT=8003
export CMAP_GENE_INFO_PATH=/data2/wanggang/camp/level5/GSE92742_Broad_LINCS_gene_info.txt.gz
```

v2 `start_v2.sh` 的固定参数【实测】：

```bash
export DATA_PROVIDER=l5
export CMAP_DATA_DIR=/home/keji/cmap_v2_data
export LMNA_CACHE_DIR=/home/keji/lmna_v2_cache
export BOOTSTRAP_N=100000
export FDR_THRESHOLD=0.001
export KS_THRESHOLD=0.2
export FAST_MODE_TOP_N=0
export DRUG_NULL_N=10000
export API_PORT=8004
export LMNA_CORS_ORIGINS=https://10.39.15.238:8084
# 若 LMNA_ADMIN_TOKEN 未设置且 ~/lmna_v2/.admin_token 存在，则从文件读取
```

注意：v2 **部署参数**是论文模式（FDR 0.001、Bootstrap 100000），但仓库默认值是 FDR 0.05、Bootstrap 1000。描述“默认行为”时必须区分“代码默认”和“当前部署值”。

### 1.6 回滚

部署报告第 7 节原文【日志/报告】：

```bash
bash ~/stop_new_instances.sh
# 如需彻底删除（不影响老服务）：
rm -rf ~/cmap_v2 ~/lmna_v2 ~/Easy_R_v2_next \
       ~/cmap_v2_data ~/lmna_v2_cache ~/cmap_v2_temp \
       ~/Easy_R_v2_next_data ~/Easy_R_v2_next_secrets ~/lmna_v2_verify
```

LMNA 自身的回滚只需要：

```bash
bash ~/lmna_v2/stop_frontend_v2.sh
bash ~/lmna_v2/stop_v2.sh
# 确认 8004/8084 已释放
ss -tln | grep -E ':8004|:8084' || true
```

彻底删除 v2 LMNA（不影响 v1/cmap）：

```bash
rm -rf ~/lmna_v2 ~/lmna_v2_cache ~/lmna_v2_verify
```

红线：上面的 `rm -rf` 是破坏性操作，只能在确认不再需要 v2 缓存/代码时由人执行；不要删除共享 `~/cmap/cmap_data`（v1/cmap/cmap_v2 都依赖它）。

### 1.7 v1 与 v2 的关键差异（先看这张表）

| 维度 | v1（现网） | v2（8d367b6） |
|---|---|---|
| 数据层级 | sh 侧 L3 自建 ZSVC + drug 侧 L4 ZSPCINF | GSE92742 Level5 `fast_matrix.npy` |
| 数据提供者 | `l4zsvc`（`L4ZSVCProvider`） | `l5`（`L5Provider`） |
| 签名统计 | GSEA 式单侧 ES_up/ES_down | 带符号 KS |
| Bootstrap | 有放回、不排除目标基因列 | 无放回、排除目标基因列 |
| 默认阈值 | FDR 0.001、Bootstrap 100000、KS 0.2 | 代码默认 FDR 0.05/B=1000；v2 部署覆盖为 0.001/100000 |
| 药物范围 | FDA 药物（651 种，235,433 实例） | 全部 `trt_cp`（19,811 种） |
| 药物打分 | 实例级 XSUM + 掩码 + 置换 p（仅 p_value） | 药物中位数 XSUM + 随机签名 null（p/FDR/null_z） |
| 药物方向 | 默认逆转（top score<0） | `lof`/`gof` 双模式 |
| 适用性判档 | 无 | 红/黄/绿 + LOHO + 可选注释 |
| 缓存版本化 | 无（固定文件名） | 参数哈希 + ALGO_VERSION + 文件锁 + 原子写 |
| 任务去重/超时/鉴权 | 无 | 有（进程内锁、7200s 超时、X-Admin-Token） |
| 导出/Figure3/Touchstone | 有 | 无 |
| 前端 | 方法选择、Figure3、Top/Bottom、P 值、Touchstone、三种导出 | 方法选择、Top/Bottom、Score、JSON/CSV 导出；**无 qc/FDR/适用性 UI** |

---

## 2. 后端架构与模块清单

### 2.1 启动与单例装配

`backend/main.py` 是唯一入口：

1. 把 `backend/` 加入 `sys.path`（`main.py:11-12`），因此模块之间是裸 import，运行目录必须是 `backend/`。
2. 读取 `config.py`，创建全局单例（`main.py:59-62`）：
   - `_provider = create_provider()`：默认 `l5`；
   - `_cache = CacheManager()`；
   - `_queue = TaskQueue()`。
3. CORS 从 `LMNA_CORS_ORIGINS` 读取，逗号分隔；为空则**不添加** CORS 中间件（`main.py:33-57`）。
4. `@app.on_event("startup")` 调用 `_queue.mark_stale_tasks_on_startup()`，把上次进程残留的 pending/running 任务标为 failed（`main.py:65-68`）。
5. `if __name__ == "__main__"` 用 uvicorn 启动，host/port 来自 `API_HOST`/`API_PORT`（`main.py:308-310`）。

v2 由 `python3 -m uvicorn main:app --ssl-certfile ... --ssl-keyfile ...` 启动，不执行 `main.py` 的 `__main__` 分支；`start_v2.sh:41-45`。

### 2.2 模块清单（按职责）

| 文件 | 职责 | 关键函数/类（行号） | 备注 |
|---|---|---|---|
| `backend/main.py` | FastAPI 路由、请求模型、单例装配 | `ComputeRequest` 73-76；`DrugQueryRequest` 78-83；`health` 88-95；`list_genes` 98-105；`gene_status` 108-120；`gene_suitability` 123-142；`compute_gene` 145-197；`get_task` 200-206；`list_tasks` 209-212；`get_signature` 215-239；`get_drugs` 242-276；`clear_cache` 279-303 | `DrugQueryRequest` 定义但未使用；`/drugs` 用查询参数 |
| `backend/config.py` | 路径、维度、算法参数、环境变量 | 路径 10-37；维度 30-31；`ALGO_VERSION` 46；阈值 49-60；D4 66-68；判档 71-77；药物 80-85；API/任务/安全 88-103；`signature_params` 106-119 | 所有可复现参数进入缓存键 |
| `backend/data_provider.py` | 数据提供者抽象接口 | `IDataProvider` 13；10 个抽象方法 16-121 | v1/v2 provider 的共同契约 |
| `backend/provider_factory.py` | provider 工厂 | `create_provider` 17-43 | `l5`→L5；`l3` 立即 NotImplementedError；`fixture`→Fixture；未知→ValueError |
| `backend/l5_provider.py` | Level5 数据读取 | `L5Provider` 27；单例 `__new__` 35；初始化 40-114；列序哨兵 61-66；行映射 70-88；shRNA/drug 过滤 102-108；`get_expression_matrix` 130-145；`list_available_genes` 165-167 | 列序哨兵 `CHECK_COL_ORDER=True` 24 |
| `backend/l3_provider.py` | L3 占位 | 所有方法 `NotImplementedError` 22-60 | L7e 设计文档有方案，未实施 |
| `backend/fixture_provider.py` | 测试夹具 provider | `FixtureProvider` 33；初始化 36-90；接口 109-176；`get_target_inhibitors` 176 | 读 `LMNA_FIXTURE_DIR` 下的 `lmna_fixture.npz` + TSV + meta |
| `backend/signature_engine.py` | 签名计算、Bootstrap、BH、秩缓存 | 秩缓存 34-127；`ks_uniform_batch` 130-143；`SignatureEngine` 146；`compute_signature` 166-318；`_bootstrap_null_ks` 320-361；`_benjamini_hochberg` 364-379 | 核心统计实现 |
| `backend/suitability.py` | 适用性预检、LOHO、判档、注释 | `RULE_VERSION` 35；`load_annotation` 59-123；`precheck` 126-189；`loho_jaccard_min` 192-260；`grade` 263-439 | 规则 4.4-rev |
| `backend/drug_median_cache.py` | 药物中位数矩阵缓存 | 版本化路径 22-29；加载 32-46；构建 49-134；入口 137-139 | 978 × n_drug，按药物名分组取中位数 |
| `backend/drug_scorer.py` | XSUM/WTCS 打分、药物 null | 符号约定 10-14；`DrugScorer` 39；`score_drugs` 48-76；`drug_null` 82-204；`_select_ends` 211-222；`_xsum_score` 224-291；`_wtcs_score` 293-343；`_drug_records` 345-359 | XSUM 带 p/FDR；WTCS 的 null 字段为 None |
| `backend/cache_manager.py` | JSON 缓存、文件锁、原子写、缓存键 | `exclusive_file_lock` 36-65；`signature_params_hash` 73-78；`replace_file_with_retry` 81-92；`read_json_file` 95-110；`atomic_write_json` 113-131；`signature_path` 157-162；`drug_scores_filename` 164-179；`_find_drug_scores_path` 212-272；`clear_gene` 329-353 | 缓存文件名的唯一构造入口 |
| `backend/task_queue.py` | 任务提交、去重、进程池、超时 | `_dedup_identity` 71-101；`_get_executor` 104-109；`_compute_task_worker` 117-208；`_update_task_status` 211-231；`TaskQueue` 234；`_find_active_task` 242-277；`submit_ex` 293-362；`get_status` 364-380；`mark_stale_tasks_on_startup` 382-408；`list_tasks` 410-422 | `max_workers=2`；JSON 任务文件 |
| `backend/tests/` | pytest 测试 | 16 个文件 | 夹具路径见第 8 章 |

### 2.3 API 清单（字段级）

所有响应均为 JSON；`gene_name` 一律转大写。

#### `GET /api/health`（`main.py:88-95`）

```json
{
  "status": "ok",
  "provider": "l5",
  "available_genes": 4371,
  "cached_signatures": 1
}
```

v2 实测值 `available_genes=4371`、`cached_signatures=1`；v1 实测 `provider=l4zsvc`、`available_genes=4435`、`cached_signatures=2`。

#### `GET /api/genes?query=TP5`（`main.py:98-105`）

- `query` 可选，前缀匹配（`startswith`），大小写不敏感。
- 响应：`{"genes": [...最多 500 个...], "total": N}`。`total` 是过滤后的总数，不是返回数。

#### `GET /api/genes/{gene_name}/status`（`main.py:108-120`）

```json
{
  "gene_name": "TP53",
  "available": true,
  "n_shrna_samples": 71,
  "pert_types": {"trt_sh": 71},
  "cached": true
}
```

- `available = n_shrna_samples >= MIN_SH_SAMPLES`（默认 3）。
- `pert_types` 是 `value_counts().to_dict()`；无样本时为 `{}`。

#### `GET /api/genes/{gene_name}/suitability`（`main.py:123-142`，L3 新增）

```json
{
  "gene_name": "TP53",
  "precheck": {
    "gene_name": "TP53",
    "n_samples": 71,
    "n_hairpins": 7,
    "n_cells": 12,
    "cell_lines": ["A375", "..."],
    "data_gate_ok": true,
    "reasons": ["数据前置门槛通过：71 个样本、7 个 hairpin、12 个细胞系"]
  },
  "qc": { "...签名缓存里的判档对象..." },
  "grade": "yellow",
  "cached_signature": true
}
```

- 无缓存签名时 `qc=null`、`grade=null`，`precheck` 仍返回。
- 无样本时 HTTP 仍为 200，`n_samples=0`、`data_gate_ok=false`。

#### `POST /api/genes/{gene_name}/compute`（`main.py:145-197`）

请求体：

```json
{"method": "xsum", "mode": "lof"}
```

- `method`：`"xsum"`（默认）或 `"wtcs"`；大小写不敏感，非法值 400。
- `mode`：`"lof"`（默认，找逆转药）或 `"gof"`（找模拟药）。
- 校验顺序：
  1. `n_samples == 0` → 404；
  2. `n_hairpins < SUITABILITY_MIN_HAIRPINS`（默认 2）→ 422；
  3. `n_samples < MIN_SH_SAMPLES`（默认 3）→ 422；
  4. 非法 method → 400。
- 成功响应：`task_id, gene_name, method, mode, status, deduplicated`。
- `deduplicated=true` 表示复用了同一基因/方法/score_mode/参数哈希的 pending/running 任务。

#### `GET /api/tasks/{task_id}`（`main.py:200-206`）

- 返回任务 JSON；不存在 404。
- 任务 JSON 字段见 2.5。
- `running` 且超过 `TASK_TIMEOUT_SEC` 未更新时，`get_status` 会就地标为 failed（`task_queue.py:364-380`）。

#### `GET /api/tasks?limit=20`（`main.py:209-212`）

- 响应：`{"tasks": [...]}`，按 `created_at` 倒序（`task_queue.py:410-422`）。

#### `GET /api/genes/{gene_name}/signature`（`main.py:215-239`）

```json
{
  "gene_name": "TP53",
  "n_samples": 71,
  "n_sig": 43,
  "n_up_genes": 19,
  "n_down_genes": 24,
  "up_genes": ["..."],
  "down_genes": ["..."],
  "bootstrap_n": 100000,
  "fast_mode": false,
  "params": {"ALGO_VERSION": "2", "...": "..."},
  "qc": {"grade": "yellow", "...": "..."},
  "n_hairpins": 7,
  "n_cells": 12
}
```

- 无缓存签名 404。
- `n_sig` 是**封顶前**通过 FDR+KS 的基因数；`n_up_genes`/`n_down_genes` 是封顶后的列表长度。
- 旧缓存没有 `qc`/`n_hairpins`/`n_cells` 时分别返回 `null`/`null`/`null`。

#### `GET /api/genes/{gene_name}/drugs`（`main.py:242-276`）

查询参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `method` | `xsum` | `xsum`/`wtcs` |
| `mode` | `lof` | `lof`/`gof`，同时决定缓存文件名 |
| `include_red` | `false` | `qc.grade=red` 时是否仍返回药物列表 |
| `top_n` | 50 | top 列表长度 |
| `bottom_n` | 50 | bottom 列表长度 |

响应：

```json
{
  "gene_name": "TP53",
  "method": "xsum",
  "mode": "lof",
  "n_up_genes": 19,
  "n_down_genes": 24,
  "top_drugs": [
    {
      "drug_name": "BRD-K59550348",
      "score": 24.8246,
      "p_reversal": 0.0004,
      "fdr_reversal": 0.990451,
      "p_mimic": 0.9997,
      "fdr_mimic": 0.999902,
      "null_z": -3.4347
    }
  ],
  "bottom_drugs": ["..."],
  "qc": {"grade": "yellow", "...": "..."},
  "include_red": false,
  "red_suppressed": false
}
```

- 只有 `top_drugs`/`bottom_drugs` 会按 `top_n`/`bottom_n` 截断；`all_scores` 不通过该 HTTP 接口返回。
- `qc.grade=red` 且 `include_red=false` 时，`top_drugs`/`bottom_drugs` 均为 `[]`，`red_suppressed=true`。
- WTCS 的 `p_reversal/fdr_reversal/p_mimic/fdr_mimic/null_z` 全部为 `null`。

#### `DELETE /api/cache/{gene_name}`（`main.py:279-303`）

- 必须带 `X-Admin-Token`。
- `LMNA_ADMIN_TOKEN` 未配置时，即使带 header 也 403。
- 正确 token 返回 `{gene_name, deleted, message}`；`deleted=false` 表示本来无缓存。
- token 比较用 `secrets.compare_digest`。

### 2.4 请求模型的两个“坑”

1. `DrugQueryRequest`（`main.py:78-83`）是死代码，`/drugs` 实际用查询参数；改字段时不要只改这个模型。
2. `ComputeRequest` 只有 `method` 和 `mode`；`top_k`/`bottom_k` 不在计算请求里，由 `/drugs` 的 `top_n`/`bottom_n` 控制展示，缓存里默认已算 50/50。

### 2.5 任务执行与文件格式

`TaskQueue.submit_ex`（`task_queue.py:293-362`）流程：

1. 归一化 gene/method/score_mode；
2. 计算 `dedup_key`、`mode(fast|full)`、`params_hash`（`_dedup_identity` 71-101）；
3. 在进程内 `_submit_lock` 下查找同 `dedup_key` 的 pending/running 任务；命中直接返回 `(task_id, True)`；
4. 生成 `task_id = str(uuid.uuid4())[:16]`；
5. 原子写初始任务 JSON；
6. `LMNA_TASK_INLINE=1` 时同进程执行，否则提交给 `ProcessPoolExecutor(max_workers=2)`。

任务 JSON 字段：

```json
{
  "task_id": "f303296a-1c91-4c",
  "gene_name": "TP53",
  "method": "xsum",
  "status": "pending|running|completed|failed",
  "created_at": "2026-10-18T01:47:26.994702",
  "updated_at": "2026-10-18T01:53:29.377209",
  "message": "计算完成",
  "mode": "full",
  "score_mode": "lof",
  "params_hash": "16 位 sha256",
  "dedup_key": "32 位 sha256",
  "result": { "...完成时..." },
  "error": "失败时..."
}
```

- `mode` 是签名模式（`fast`/`full`），不是 `lof/gof`；`score_mode` 才是药物方向。
- `pending` 没有超时；只有 `running` 有 `TASK_TIMEOUT_SEC` 心跳超时。
- 启动时 `mark_stale_tasks_on_startup` 把所有 pending/running 标 failed（`task_queue.py:382-408`）。
- 去重锁是**进程内** `threading.Lock`；按单 worker/多线程部署可用，多进程部署需要文件锁/数据库（见第 9 章）。

`_compute_task_worker`（`task_queue.py:117-208`）执行顺序：

1. 标 running；
2. 读签名缓存（带参数哈希），没有则 `SignatureEngine.compute_signature` 并保存；
3. 读药物缓存（带 `fast/normal` + `lof/gof`），没有则 `DrugScorer.score_drugs` 并保存；
4. 读签名 `qc`，红档默认屏蔽；
5. 组装 `result.signature` + `result.drug_results`，标 completed。

任务结果结构：

```json
{
  "signature": {
    "gene_name": "TP53",
    "n_samples": 71,
    "n_sig": 43,
    "n_up_genes": 19,
    "n_down_genes": 24,
    "up_genes": ["..."],
    "down_genes": ["..."],
    "fast_mode": false,
    "params": {"...": "..."},
    "qc": {"...": "..."},
    "n_hairpins": 7,
    "n_cells": 12
  },
  "drug_results": {
    "method": "xsum",
    "mode": "lof",
    "top_drugs": ["..."],
    "bottom_drugs": ["..."],
    "qc": {"...": "..."},
    "red_suppressed": false
  }
}
```

任务结果**不包含** `all_scores` 和 `null_params`；它们只在药物缓存 JSON 里。

药物缓存 JSON（`cache/drug_scores/`）：

```json
{
  "method": "xsum",
  "mode": "lof",
  "gene_name": "TP53",
  "n_up_genes": 19,
  "n_down_genes": 24,
  "null_params": {"M": 10000, "batch": 500, "seed": 42},
  "top_drugs": ["..."],
  "bottom_drugs": ["..."],
  "all_scores": ["...19,811 条..."]
}
```

v2 TP53 药物缓存实测：`all_scores` 19,811 条，文件 5,227,185 B。

### 2.6 配置项总表

| 环境变量/常量 | 默认 | 位置 | 说明 |
|---|---|---|---|
| `CMAP_DATA_DIR` | `<repo>/../cmap_data` | `config.py:17` | 数据目录 |
| `LMNA_CACHE_DIR` | `<repo>/cache` | `config.py:34` | 缓存根目录 |
| `DATA_PROVIDER` | `l5` | `config.py:93` | `l5`/`l3`/`fixture`；`l3` 启动即失败 |
| `ALGO_VERSION` | `"2"` | `config.py:46` | 算法版本，参与缓存名 |
| `MIN_SH_SAMPLES` | 3 | `config.py:49` | 最少 shRNA 样本 |
| `KS_THRESHOLD` | 0.2 | `config.py:50` | \|KS\| 阈值 |
| `FDR_THRESHOLD` | 0.05 | `config.py:51` | BH FDR 阈值；论文模式 0.001 |
| `BOOTSTRAP_N` | 1000 | `config.py:52` | Bootstrap 次数；论文模式 100000 |
| `RANDOM_SEED` | 42 | `config.py:53` | 固定种子 |
| `MAX_GENES_PER_DIRECTION` | 50 | `config.py:56` | 每方向封顶；0=不封顶 |
| `FAST_MODE_TOP_N` | 0 | `config.py:60` | 快速模式；0=关闭 |
| `GENE_ANNOTATIONS_PATH` | `DATA_DIR/gene_annotations.tsv` | `config.py:66-68` | D4 注释表 |
| `SUITABILITY_MIN_HAIRPINS` | 2 | `config.py:71` | 判档/计算门槛 |
| `SUITABILITY_MIN_SIG` | 5 | `config.py:72` | 绿档最低 n_sig |
| `SUITABILITY_YELLOW_MIN_SIG` | 20 | `config.py:73` | 黄档最低 n_sig |
| `SUITABILITY_JACCARD_GREEN` | 0.5 | `config.py:74` | 绿档 LOHO 下限 |
| `SUITABILITY_JACCARD_RED` | 0.3 | `config.py:75` | 红档 LOHO 上限 |
| `LOHO_MIN_REMAINING` | 3 | `config.py:77` | 留一后最少剩余样本 |
| `DEFAULT_TOP_K` / `DEFAULT_BOTTOM_K` | 50 / 50 | `config.py:80-81` | 缓存默认 top/bottom 长度 |
| `DRUG_NULL_N` | 10000 | `config.py:85` | 药物随机签名数 |
| `API_HOST` | `0.0.0.0` | `config.py:88` | 监听地址 |
| `API_PORT` | 8001 | `config.py:89` | 监听端口 |
| `TASK_TIMEOUT_SEC` | 7200 | `config.py:97` | running 心跳超时 |
| `LMNA_ADMIN_TOKEN` | 空 | `config.py:101` | 删除缓存令牌 |
| `LMNA_CORS_ORIGINS` | 空 | `config.py:103` | 逗号分隔；空=不启用 CORS |
| `LMNA_TASK_INLINE` | 未设置 | `task_queue.py:338` | 测试用同进程执行 |

`signature_params()`（`config.py:106-119`）包含：`ALGO_VERSION`、`DATA_PROVIDER`、`KS_THRESHOLD`、`FDR_THRESHOLD`、`BOOTSTRAP_N`、`RANDOM_SEED`、`FAST_MODE_TOP_N`、`MAX_GENES_PER_DIRECTION`、`DRUG_NULL_N`。任何一项变化都会改变缓存哈希。

---

## 3. 数据层全景

### 3.1 `cmap_data` 的文件与语义

共享目录 `~/cmap/cmap_data` 的核心文件【实测】：

| 文件 | 大小 | 作用 |
|---|---:|---|
| `fast_matrix.npy` | 23,356,480,864 B（23.36 GB） | float32，shape `(12328, 473647)`；行=基因，列=签名 |
| `GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx` | 23,380,287,022 B | 原始 Level5 GCTX；`fast_matrix` 的列/行序真值来源 |
| `col_sig_ids.csv` | 17,907,075 B（旧）/17,433,427 B（v2 修正） | `sig_id` 列表，一列 `sig_id` |
| `row_gene_ids.csv` | 79,847 B（旧）/67,518 B（v2 修正） | `gene_id` 列表，一列 `gene_id` |
| `GSE92742_Broad_LINCS_sig_info.txt.gz` | 11,124,404 B | 签名元数据：`sig_id/pert_id/pert_iname/pert_type/cell_id/distil_id` 等 |
| `GSE92742_Broad_LINCS_gene_info.txt.gz` | 216,692 B | 基因元数据：`pr_gene_id/pr_gene_symbol/pr_is_lm` |
| `GSE92742_Broad_LINCS_pert_info.txt.gz` | 1,138,509 B | 扰动元数据 |
| `GSE92742_Broad_LINCS_cell_info.txt.gz` | 2,528 B | 细胞系元数据 |

### 3.2 `fast_matrix.npy` 与 GCTX 的关系（真值定义）

【实测】【日志/报告】

```text
fast_matrix.npy 的列序 = GCTX 0/META/COL/id 的顺序
fast_matrix.npy 的行序 = GCTX 0/META/ROW/id 的顺序
fast_matrix[k, j]      = GCTX[0/DATA/0/matrix][j, k]   （k=列/签名，j=行/基因）
```

- `col_sig_ids.csv` 的语义必须是“第 i 行 = 矩阵第 i 列的 sig_id”；
- `row_gene_ids.csv` 的语义必须是“第 i 行 = 矩阵第 i 行的 gene_id”；
- `L5Provider` 用这两个 CSV 建 `sig_id -> 列索引` 和 `gene_id -> 行索引`；
- `get_expression_matrix` 取 `matrix[:, idx_chunk]` 后再用 `_lm_indices` 取 978 个 landmark 行（`l5_provider.py:130-145`）。

### 3.3 L8 列序/行序 bug 与修复

#### 症状

旧 `col_sig_ids.csv` 是按 `sig_id` 字典序排序的，而矩阵列是 GCTX COL 顺序。两者集合相同，但位置完全不同：

- 列：同位置一致 **3/473,647**；旧首项 `AML001_CD34_24H:A05`，GCTX 首项 `CPC005_A375_6H:BRD-A85280935-003-01-7:10`。
- 行：同位置一致 **4/12,328**；旧首项 `780`（gene_info 顺序），GCTX 首项 `5720`；978 个 landmark 基因位置 **0/978** 相同。

后果：

- 按旧 CSV 取列会读到别的签名，且不会报错；
- 只修列不修行，978 维表达向量仍取到错误基因，药物中位数矩阵整行错位；
- 实测旧映射的 978 维向量与 GCTX 真值相关系数约 `0.003 / -0.002 / -0.016`，近似不相关（L8 交付）。

#### 修复

`scripts/fix_col_names.py`（234 行）：

- 默认只读 GCTX 的 `0/META/COL/id` 和 `0/META/ROW/id`，不读 23 GB 数据；
- 默认 `--data-dir ~/cmap/cmap_data`；
- `--check` 只诊断不写；
- `--in-place` 备份后原地替换 `col_sig_ids.csv`；
- `--fix-rows` 同时修 `row_gene_ids.csv`（L8 额外发现，默认关闭）；
- `--verify N` 抽样校验 `fast_matrix[:, k]` 与 `GCTX[k, :]`，默认 3 列；
- 原子写 CSV，备份名 `.bak-<timestamp>`；
- 若 GCTX 有重复 COL/ROW id 直接退出。

部署时执行的是：

```bash
python scripts/fix_col_names.py --data-dir ~/cmap/cmap_data --in-place --fix-rows
```

v2 的实际执行目录是 `~/cmap_v2_data`（不是共享目录），结果见 1.3。

#### 修复后的验证

【日志/报告】

```text
col_sig_ids.csv: 473647/473647 与 GCTX COL 顺序一致（修复前 3/473647）
row_gene_ids.csv: 12328/12328 与 GCTX ROW 顺序一致（修复前 4/12328）
抽样列校验: 5 个 sig_id max|diff| = 0.000e+00
药物中位数 (978, 19811) 复核: min=1.0000 median=1.0000 max=1.0000，全部 r >= 0.99
```

#### 当前修复范围（非常重要）

- **v2 专属副本已修**：`~/cmap_v2_data` 的 col/row CSV 正确，`fast_matrix`/GCTX 是软链接。
- **共享 `~/cmap/cmap_data` 未修**：仍是旧字典序/旧行序；老 cmap、任何使用共享目录的 v1 L5 路径仍会读错。
- **v1 生产不受影响**：v1 生产 `DATA_PROVIDER=l4zsvc`，`L4ZSVCProvider` 读 `/data2/wanggang/camp/level3/level4` 的 GCTX，不读 `fast_matrix.npy`/这两个 CSV【代码】【实测】。
- **v1 的 `l5_provider.py` 仍受影响**：如果改 `DATA_PROVIDER=l5` 且指向共享目录，L8 bug 会立即出现。

### 3.4 缓存全景与版本化

#### 目录

```text
$LMNA_CACHE_DIR/
├── signatures/                  # 签名 JSON
├── drug_scores/                 # 药物结果 JSON
├── tasks/                       # 任务 JSON
├── _shrna_rank_matrix.v2.<n_shrna>.dat
├── _shrna_rank_matrix.v2.<n_shrna>.shape.txt
├── _drug_median_matrix.v2.npy
├── _drug_names.v2.csv
└── *.lock                       # 构建锁（空文件/1 字节）
```

#### 文件名规则

| 缓存 | 文件名 | 代码 |
|---|---|---|
| 签名 | `{GENE}_{h}_signature.json` | `cache_manager.py:157-162` |
| 药物 | `{GENE}_{h}_{method}_{fast}_{score}_drug_scores.json` | `cache_manager.py:164-179` |
| 秩矩阵 | `_shrna_rank_matrix.v{ALGO_VERSION}.{n_shrna}.dat` | `signature_engine.py:34-41` |
| 药物中位数 | `_drug_median_matrix.v{ALGO_VERSION}.npy` | `drug_median_cache.py:22-29` |
| 药物名 | `_drug_names.v{ALGO_VERSION}.csv` | `drug_median_cache.py:22-29` |

其中：

```text
h = sha1(json.dumps(signature_params(), sort_keys=True))[:10]
fast = "fast" | "normal"
score = "lof" | "gof"
n_shrna = 当前 provider 的 trt_sh 样本数
```

v2 实测：`h=b031a48b8a`，`TP53_b031a48b8a_signature.json`、`TP53_b031a48b8a_xsum_normal_lof_drug_scores.json`。

#### 版本化与并发安全

- 参数哈希变化 → 旧签名/药物缓存文件名不同 → 不会误读（L2）。
- `ALGO_VERSION` 变化 → 秩/药物中位数缓存自动换名（L2）。
- 秩矩阵和药物中位数都有 `.lock` + 双重检查 + 临时文件原子替换（`signature_engine.py:82-125`、`drug_median_cache.py:66-134`）。
- JSON 写入用 `atomic_write_json`：临时文件名带 pid+随机后缀，`os.replace` 原子替换（`cache_manager.py:113-131`）。
- `read_json_file` 对 Windows 的短暂 `PermissionError` 重试 20 次，对损坏 JSON 返回 `None`（`cache_manager.py:95-110`）。
- 药物缓存读取有回退：`fast_mode` 未指定时 `normal > fast`，`score_mode` 未指定时 `lof > gof`（`cache_manager.py:212-272`）；旧命名（无哈希）不参与读取，但 `clear_gene` 会清理。

#### v2 缓存实测

| 文件 | 大小 | 形状/内容 |
|---|---:|---|
| `_drug_median_matrix.v2.npy` | 77,500,760 B | `(978, 19811)` float32 |
| `_drug_names.v2.csv` | 268,566 B | 19,811 个药物名 |
| `_shrna_rank_matrix.v2.154993.dat` | 303,166,308 B | int16 `(978, 154993)` |
| `_shrna_rank_matrix.v2.154993.shape.txt` | 10 B | `978,154993` |
| `TP53_b031a48b8a_signature.json` | 163,981 B | TP53 签名 |
| `TP53_b031a48b8a_xsum_normal_lof_drug_scores.json` | 5,227,185 B | 19,811 条 all_scores |

注意：v2 的 shRNA 池是 **154,993**，不是 v1 的 376,415；这是因为 v2 用 GSE92742 Level5 的 `trt_sh` 全量，而 v1 用 L4 `is_gold` + ZSVC 池。两者不可直接比较缓存大小。

---

## 4. v1 现状（现网 `~/lmna_app/LMNA`）

### 4.1 代码与数据源

v1 目录下的后端文件【实测】：

```text
backend/
├── main.py                 # 路由（含 figure3/export/touchstone）
├── config.py               # 数据源、论文参数
├── l4zsvc_provider.py      # 生产 provider：L4 + ZSVC sh 侧
├── l4_provider.py          # L4 ZSPCINF + is_gold + FDA
├── l3_provider.py          # L3（vehicle 重算）
├── l5_provider.py          # L5（历史路径，当前未用于生产）
├── drug_scorer.py          # 实例级 XSUM + 置换 p；WTCS
├── signature_engine.py     # GSEA 式 ES_up/ES_down + Bootstrap
├── task_queue.py           # JSON 任务 + ProcessPool
├── cache_manager.py        # 固定文件名缓存（无版本化）
├── export_store.py         # 导出 token（文件 + 内存，TTL 300s）
├── figure3_replica.py      # Figure3 复现图
├── check_status.py         # 数据/缓存状态检查
├── chatgpt_template.py     # 模板/文本辅助
├── fda_drugs.txt           # 662 FDA + 2 CMAP 补充
├── trt_sh_isgold.csv       # 论文 is_gold 映射
└── lmna.crt / lmna.key     # HTTPS 证书（本文不引用内容）
```

v1 数据源【代码】【实测】：

| 用途 | 路径/文件 | 过滤 |
|---|---|---|
| shRNA 表达 | `/data2/wanggang/camp/level4/level4_beta_trt_sh_n453175x12328.gctx`（22.35 GB） | `is_gold` 优先，未覆盖回退 `qc_pass`；`pert_type` 以 `trt_sh` 开头 |
| 药物表达 | `/data2/wanggang/camp/level4/level4_beta_trt_cp_n1805898x12328.gctx`（89.06 GB） | `qc_pass=1` + FDA 名单（651 种，235,433 实例） |
| 元数据 | `/data2/wanggang/camp/level4/instinfo_beta.txt` | — |
| ZSVC sh 侧 | `cache/_l4zsvc_shrna_z.dat`（978 × 376,415） | `analysis/zsvc_build.py` 从 L3 原始值重建 |
| ZSVC 构建输入 | `/data2/wanggang/camp/level3/GSE92742_Broad_LINCS_Level3_INF_mlr12k_n1319138x12328.gctx`、`inst_info`、`level3_beta_trt_sh_n453175x12328.gctx` | 同板 `ctl_vector` mean/std（ddof=1），<3 孔回退细胞系，再回退全局 |

`zsvc_build.log` 关键数字【日志/报告】：

```text
池大小: 376415
Phase I 样本: 368973, Phase II: 7442
对照孔 vector+untrt（池涉及板）: 43370
板级统计: 1413 板（1304 板 >= 3 孔）
细胞系统计: 20 个细胞系
z memmap: (376415, 978)
drug(qc_pass)=1312170, FDA drug=235433 (651 种), LM genes=978
```

注意：v1 实际数据在 `/data2/wanggang/camp`，不是 `~/cmap/cmap_data`。`~/lmna_app/cmap_data` 只是小目录（元数据/符号链接），不要据此判断 v1 的数据来源。

### 4.2 v1 路由

v1 `main.py` 的路由【代码】：

| 方法/路径 | 作用 | 与 v2 的差异 |
|---|---|---|
| `GET /` | 同源返回 `frontend/index.html` | v2 没有静态挂载，前端由独立服务提供 |
| `GET /echarts.min.js` | 本地 ECharts | v2 无 |
| `GET /api/health` | 健康检查 | 字段相同 |
| `GET /api/genes` | 基因列表 | 字段相同 |
| `GET /api/genes/{gene}/status` | 可用性（`n>=3`） | v1 没有 hairpin 门槛 |
| `POST /api/genes/{gene}/compute` | 提交任务，body 只有 `method` | v2 有 `mode`、hairpin 422、去重 |
| `GET /api/tasks/{id}` | 任务状态 | v1 额外注入 `is_touchstone` |
| `GET /api/tasks` | 任务列表 | 相同 |
| `GET /api/genes/{gene}/signature` | 签名 | v1 无 `n_sig/qc/n_hairpins/n_cells/params` |
| `GET /api/genes/{gene}/drugs` | 药物结果 | v1 无 `mode/include_red/red_suppressed/qc`；返回 `is_touchstone` |
| `DELETE /api/cache/{gene}` | 清缓存 | **v1 无鉴权** |
| `GET /api/genes/{gene}/figure3` | 完整 Figure3 PNG | v2 无 |
| `GET /api/genes/{gene}/figure3/{a,b,c}` | 单面板 PNG | v2 无 |
| `GET /api/genes/{gene}/signature/export` | 签名 CSV | v2 无 |
| `POST /api/export_data` | 提交导出数据，返回 token | v2 无 |
| `GET /api/export_data/{token}` | 一次性下载 ZIP | v2 无 |

### 4.3 v1 前端按钮与 API 映射

v1 `frontend/index.html`【代码】：

| UI | 动作 | 后端 |
|---|---|---|
| 基因名输入 | — | — |
| 筛药方法下拉 | `XSUM（论文方法）` / `WTCS（连接图方法）` | `POST /compute {"method": ...}` |
| 开始计算 | 提交并 3 秒轮询 | `POST /api/genes/{gene}/compute`、`GET /api/tasks/{id}` |
| 检查数据 | 查可用性 | `GET /api/genes/{gene}/status` |
| 任务状态/进度条 | 轮询 | 同上 |
| Figure 3 复现 | 加载 A/B/C 三张图 | `GET /figure3/a|b|c?method=` |
| 得分分布 | ECharts 散点 | 使用任务结果里的 `all_scores`/top/bottom |
| Top 逆转药物 / Bottom 药物 | 切换表格 | `drugs.top_drugs` / `drugs.bottom_drugs` |
| 导出 ZIP | 先 POST 再跳转 | `POST /api/export_data` → `GET /api/export_data/{token}` |
| 导出签名 CSV | 直接下载 | `GET /api/genes/{gene}/signature/export` |
| 导出 JSON | 浏览器本地 Blob | 无后端 |
| Touchstone 列 | 展示 `is_touchstone` | 后端注入 |

**v1 没有 FDA 按钮/开关。** FDA 是 `L4Provider`/`L4ZSVCProvider` 内部的药物范围过滤（`fda_drugs.txt`），不是 UI 选项【代码】。这一点在旧文档/口头描述中容易被误解。

Figure3 只实现了 XSUM 路径；WTCS 没有对应的 Figure3 面板【代码】。

v1 前端 `API_BASE`（`frontend/index.html:451`）：

```javascript
const API_BASE = location.port === '8003' ? '' : 'https://10.39.15.238:8003';
```

即从 8003 访问走同源，从 8083 访问走绝对地址。

### 4.4 v1 统计口径

【代码】

- 签名：`enrichment_scores`（`signature_engine.py:85-127`）复刻论文 R 的 rank-of-ranks + GSEA 式单侧 ES_up/ES_down；`ES=0` 的 quirk 也保留。
- Bootstrap：`_bootstrap_counts`（`signature_engine.py:218+`）用 `rng.integers(0, n_pool, size=(actual, n_sample))`，**有放回**，且**不排除目标基因自身列**。
- p 值：`(count + 1) / (BOOTSTRAP_N + 1)`。
- 多重校正：up/down **各自**做 BH；签名条件 `ES > 0.2` 且 `FDR < 0.001`。
- 药物 XSUM：
  - 逐实例对 978 个 z 排名，掩码 `XSUM_MASK_N=489`，只保留最极端的两端；
  - `score = Σ masked_z[up] − Σ masked_z[down]`（注意：v1 这个符号与 v2 的 `score=-mimic` 相反，v1 top 取 `score<0`）；
  - 同一药物的多个实例取 median；
  - 置换 null：`DRUG_PERM_N=10000`，随机签名对每个药物抽样实例（每药最多 64 个实例）算 median；
  - `p = (count(null <= obs) + 1) / (perm + 1)`，**只对 `obs<0` 的药物计算**，其余 `p=1.0`；
  - 输出只有 `drug_name/score/p_value`，**没有 FDR**。
- 药物 WTCS：药物中位数矩阵的列内排名，权重 `(G+1)-2*rank`，`score = −Σw_up + Σw_down`，按最大绝对值归一化；top/bottom 只按 score 排序，无 p 值。

### 4.5 v1 缓存

【实测】

| 文件 | 大小 | 说明 |
|---|---:|---|
| `_l4zsvc_shrna_z.dat` | 1,472,535,480 B | float32 `(978, 376415)` |
| `_l4zsvc_shrna_rank_matrix.dat` | 736,267,740 B | int16 `(978, 376415)` |
| `_fda_instance_matrix_l4zsvc.npy` | 921,014,024 B | float32 `(978, 235433)` |
| `_fda_masked_matrix_l4zsvc.npy` | 921,014,024 B | XSUM 掩码后 |
| `_fda_instance_meta_l4zsvc.csv` | 10,076,901 B | 235,433 行 |
| `_xsum_null_l4zsvc_53_20.npy` | 26,040,128 B | 651 药物 × 10,000 置换（按签名规模缓存） |
| `signatures/LMNA_signature.json` | — | 84 样本、53 up / 20 down、Bootstrap 100000，**无 qc** |
| `signatures/TNFSF15_signature.json` | — | 同上 |
| `drug_scores/LMNA_xsum_drug_scores.json` | — | 651 个药物，top tramadol score -8.8995 p 0.00029997 |

v1 缓存**没有版本化**：文件名固定，改参数后可能读到旧结果；也没有原子写/文件锁（`cache_manager.py:24-65` 直接 `json.load`/`json.dump`）。这是 L1/L2 要解决的问题。

### 4.6 v1 实测状态

【实测】2026-10-18：

```json
GET https://127.0.0.1:8003/api/health
{"status":"ok","provider":"l4zsvc","available_genes":4435,"cached_signatures":2}
```

v1 LMNA 签名缓存：84 样本，53 up / 20 down，Bootstrap 100000，Fast=False。v1 LMNA 药物结果：651 个药物，top `tramadol` score -8.8995，p 0.00029997；前端 8083 返回 200。

### 4.7 v1 与 GitHub l5 的算法差异（务必不要混用结论）

| 维度 | v1 | GitHub l5 / v2 |
|---|---|---|
| shRNA 数据 | L4 ZSPCINF + `is_gold`；生产再用 ZSVC 覆盖 sh 侧 | GSE92742 Level5 MODZ |
| 签名统计量 | 单侧 ES_up/ES_down | 带符号 KS |
| Bootstrap | 有放回、不排除目标列 | 无放回、排除目标列 |
| 多重校正 | up/down 各自 BH | 全部 978 基因一套 BH |
| 阈值 | 硬编码默认 0.001/100000 | 代码默认 0.05/1000；v2 部署覆盖 0.001/100000 |
| 每方向封顶 | 无 | 50（可配） |
| 药物范围 | FDA 651 种 | 全部 `trt_cp` 19,811 种 |
| 药物打分 | 实例级 XSUM + 掩码 + 置换 p | 药物中位数 XSUM + 随机签名 null p/FDR |
| 药物方向 | 只做逆转（top score<0） | `lof`/`gof` |
| 药物显著性 | 只有 p_value | p_mimic/p_reversal/FDR/null_z |
| 缓存 | 固定文件名 | 参数哈希 + 版本 + 锁 + 原子写 |
| 任务 | 无去重/超时/鉴权 | 有 |
| 适用性 | 无 | 红/黄/绿 + LOHO |

**结论：v1 与 v2 的签名基因列表、药物排名、p/FDR 不能直接对比。** 任何“v1 结果 vs v2 结果”的分析都必须先说明数据层级和统计口径。

---

## 5. 统计方法与已知局限

### 5.1 带符号 KS（v2）

【代码】`signature_engine.py:130-143`

输入：每个样本内对 978 个 landmark 基因的秩，`1=表达最高`，`G=978`，`N=n_samples`。

```text
r_(i) = 第 i 个最小秩（升序）
D_plus  = max_i ( i/N - r_(i)/G )
D_minus = max_i ( r_(i)/G - (i-1)/N )
KS = D_plus   if D_plus >= D_minus
     -D_minus otherwise
```

符号约定：

- `KS > 0` = 敲低后该基因上调 → `up_genes`；
- `KS < 0` = 敲低后该基因下调 → `down_genes`；
- `|KS|` 用于排序和 LOHO。

### 5.2 Bootstrap p 值与 BH

【代码】`signature_engine.py:166-318`、`320-379`

1. 观测 KS：`observed_ks = ks_uniform_batch(target_ranks, G)`。
2. 目标基因列排除：按 `pert_iname == gene` 找 `exclude_cols`（`186-194`）。
3. 每次从池中**无放回**抽 `n_samples` 个样本列，算 KS；重复 `BOOTSTRAP_N` 次（`320-361`）。
4. p 值：

```text
p_g = ( #{b: |null_ks[b,g]| >= |observed_ks[g]|} + 1 ) / (B + 1)
```

这是双侧经验 p（用绝对值），不是单侧。

5. BH：

```text
q_(i) = min_{j>=i} ( p_(j) * n / j )，并 clip 到 [0,1]
```

实现为排序后 `p*n/arange(1,n+1)`，再反向累计最小值（`364-379`）。

6. 签名筛选：`fdr < FDR_THRESHOLD and abs(ks) > KS_THRESHOLD`（`228`）。
7. `n_sig` 在封顶前统计（`235`）；每方向按 KS 强度排序后封顶 `MAX_GENES_PER_DIRECTION`（`252-257`）。

### 5.3 LOHO Jaccard

【代码】`suitability.py:192-260`

- 输入：目标基因全部样本的秩矩阵 `(G, n_samples)`、每条样本的 `pert_id`、完整签名 `|KS|` 前 `k` 个基因。
- `k = max(10, len(up_genes) + len(down_genes))`（`signature_engine.py:271`），其中 up/down 是**封顶后**的列表。
- 对每个 hairpin：
  - 去掉该 hairpin 的全部样本；
  - 剩余 < `LOHO_MIN_REMAINING`（默认 3）则跳过；
  - 用剩余样本重算 KS，取 `|KS|` 前 `k`；
  - 与完整签名前 `k` 求 Jaccard = `|交集| / |并集|`。
- `loho_jaccard_min` = 所有可用 hairpin 的最小值；没有可用 hairpin 则为 `None` → 红档。
- `qc.reference` 记录 `loho_k`、`loho_hairpins_used`、`loho_hairpins_skipped`。

注意：`k` 依赖封顶后的列表长度，因此改 `MAX_GENES_PER_DIRECTION` 会改变 LOHO 和判档。

### 5.4 红/黄/绿判档

【代码】`suitability.py:263-439`，规则版本 `4.4-rev`。

判档顺序：

1. **红**（任一命中）：
   - 数据前置门槛失败（`data_gate_ok=false`，即 hairpin < 2）；
   - `n_sig < SUITABILITY_MIN_SIG`（默认 5）；
   - `fast_mode=true`；
   - `loho_jaccard_min is None`；
   - `loho_jaccard_min < 0.3`；
   - 注释显示 `expressed_in_l1000_cells=false`；
   - 注释显示 `receptor_or_channel=true` 且 `tissue_specific=true`。
2. **黄**：
   - 满足绿档但 `tissue_specific=true`；或
   - `n_sig >= 20` 且 `0.3 <= loho < 0.5`。
3. **绿**：`n_sig >= 5` 且 `loho >= 0.5`。
4. 其余 → 红（“未满足绿/黄条件”）。

关键细节：

- **注释缺失只加一条 reason，不改变档位**（`suitability.py:306-312`）。所以“缺少 `gene_annotations.tsv` 导致黄档”这个说法是**错误的**；缺注释只会让第一层显示“未知”。v2 TP53 的黄档原因是 `n_sig=43 >= 20` 且 `loho=0.34375` 落在 `[0.3, 0.5)`。
- 注释表存在但缺列/读失败/无该基因，同样只降级为“未知”，不改变档位。
- 红档时 `/drugs` 默认返回空列表，`include_red=true` 才返回。

### 5.5 药物打分：XSUM 与 WTCS（v2）

【代码】`drug_scorer.py`

符号约定（`10-14`）：

```text
mimic = Σz(up) − Σz(down)     正 = 药物模拟（mimic）查询签名
score = −mimic                高分 = 逆转（reversal）
```

#### XSUM

1. 用药物中位数矩阵 `D (978, n_drug)`（`drug_median_cache.py`）。
2. `score_vec = −Σ D[up] + Σ D[down]`（`drug_scorer.py:238-242`）。
3. 对每个药物构造随机签名 null（`drug_null`，见 5.6）。
4. 输出 `all_scores` 按 score 降序；`top_drugs`/`bottom_drugs` 按 mode + FDR 排序（`258-275`）：
   - `lof`：top 按 `fdr_reversal` 升序、再 `score` 降序；bottom 按 `fdr_mimic` 升序、再 `score` 升序；
   - `gof`：top 按 `fdr_mimic` 升序、再 `score` 升序；bottom 按 `fdr_reversal` 升序、再 `score` 降序。

#### WTCS

1. 对药物中位数矩阵每列排名，`weights = (G+1) - 2*rank`。
2. `score_vec = −Σ weights[up] + Σ weights[down]`。
3. 按最大绝对值归一化。
4. `p_reversal/fdr_reversal/p_mimic/fdr_mimic/null_z` 全为 `None`；top/bottom 只按 score 排序（`_select_ends` 211-222）。
5. WTCS **没有药物级显著性**，不要把它和 XSUM 的 FDR 混用。

### 5.6 药物级随机签名 null

【代码】`drug_scorer.py:82-204`

对每个药物，构造 `M=DRUG_NULL_N` 个与查询签名同样大小的随机签名：

- 从 `G=978` 个基因中**无放回**抽 `n_up+n_down` 个；
- 前 `n_up` 个记 `+1`，其余记 `−1`，得到权重向量 `W`；
- `null = W @ D`，`D` 是药物中位数矩阵；
- 观测 `obs_mimic = ΣD[up] − ΣD[down]`。

p 值：

```text
p_mimic    = (#{null >= obs_mimic} + 1) / (M + 1)   上尾，小 = 药物显著模拟
p_reversal = (#{null <= obs_mimic} + 1) / (M + 1)   下尾，小 = 药物显著逆转
null_z     = (obs_mimic − mean(null)) / sd(null)    sd=0 时置 0
```

FDR：

- `fdr_mimic` 和 `fdr_reversal` 分别对**全部药物**的对应 p 做 BH；
- 两个方向各一套，不合并；
- BH 复用 `SignatureEngine._benjamini_hochberg`。

计算方式：逐批 `(batch, G)` 权重矩阵和 `(batch, n_drug)` null，不会一次性构造 `(M, n_drug)`。默认 `M=10000`、`batch=500`、`seed=42`。

### 5.7 `DRUG_NULL_N=10000` 的 FDR 分辨率问题（已实测）

这是当前最容易被误判为“部署故障”的统计限制。

v2 TP53 实测【实测】：

```text
n_drug = 19,811
M = 10,000
p 下限 = 1/(M+1) = 9.999e-5
p_reversal 落在下限的药物数 = 2
fdr_reversal 最小值 = 0.9904509549
fdr_reversal 最大值 = 1.0
top: BRD-K59550348 score=24.8246 p_reversal=0.0004 fdr_reversal=0.990451
```

为什么 FDR 最小是 0.99045：

- 排序后第 1 名和第 2 名的 p 都等于 `1/10001`；
- 第 2 名的 BH 值 = `(1/10001) * 19811 / 2 ≈ 0.99045`；
- 反向累计最小值把第 1 名也压到 `0.99045`（BH 的单调性），所以最小 FDR 不是 `19811/10001≈1.98`（会被 clip 到 1），而是 0.99045。

要得到 `FDR <= 0.05`，需要：

```text
p_min * n_drug / rank <= 0.05
p_min = 1/(M+1)
```

- 若有 1 个药物落在 p 下限：`M+1 >= 19811/0.05 = 396,220` → `M >= 396,219`；
- 若有 2 个药物落在 p 下限：`M+1 >= 19811/(0.05*2) = 198,110` → `M >= 198,109`；
- 若有 k 个药物落在 p 下限：`M >= 19811/(0.05*k) - 1`。

推荐：

1. **把 `DRUG_NULL_N` 提高到至少 1,000,000**：p 下限 1e-6，单个最显著药物的 FDR 约 `19811*1e-6 = 0.0198`，可低于 0.05；计算量/内存按 L4 的分批实现近似线性增加，需实测。
2. **或限制 BH 的检验族**：例如只对“已上市/候选药物”做 BH（L7c 的 launched 集合约 1,222 个），但这会改变统计口径，必须由产品/统计负责人拍板，不能由工程擅自改。
3. **不要把 `p` 很小但 `FDR≈0.99` 解读为“药物无效”**：这是分辨率/多重校正问题，不是效应量问题；应同时报告 `score`、`null_z`、`p` 和 `FDR`。
4. **不要用 `DRUG_NULL_N` 的变化去“调显著性”**：该参数已进入 `signature_params()` 缓存键（`config.py:117-118`），改了会生成全新缓存；这是有意的，但需要同步重跑并记录。

### 5.8 D1 双模式（0.05/0.001）

`config.py:49-52`：

| 模式 | FDR_THRESHOLD | BOOTSTRAP_N | KS_THRESHOLD | 用途 |
|---|---:|---:|---:|---|
| 代码默认 | 0.05 | 1000 | 0.2 | 本地/快速验证 |
| 论文模式 | 0.001 | 100000 | 0.2 | v1 现网、v2 当前部署 |

- 代码默认值：`FDR_THRESHOLD=0.05`、`BOOTSTRAP_N=1000`（`config.py:51-52`）。
- v1 `start_server.sh` 和 v2 `start_v2.sh` 都显式 `export FDR_THRESHOLD=0.001`、`BOOTSTRAP_N=100000`。
- 因此当前两个现网实例都是论文模式；不要看 `config.py` 的默认值就以为现网是 0.05。
- 改阈值会改变 `signature_params()` → 缓存哈希变化 → 旧缓存不会命中。

### 5.9 其他统计局限

1. **Bootstrap 的 Monte Carlo 误差**：`B=100000` 时 p 的标准误约 `sqrt(p(1-p)/B)`；p 接近 0 时相对误差大。`B=1000` 只适合冒烟。
2. **p 值分辨率**：签名 p 下限 `1/(B+1)`；药物 p 下限 `1/(M+1)`。两者都不能通过“更多小数位”解决。
3. **BH 的检验族**：签名对所有 978 个基因做 BH；药物对所有 19,811 个药物做 BH。族越大，单个信号的 FDR 越高。
4. **Bootstrap 池的代表性**：v2 的池是全部 `trt_sh`（154,993 列），不按细胞系/板分层；v1 的池是 `is_gold`/ZSVC（376,415 列）。两者的 null 宽度不同。
5. **细胞系混合**：签名把所有细胞系的 shRNA 样本混在一起，未做细胞系匹配；药物也是全细胞系中位数。对细胞系特异药物可能低估。
6. **中位数先行的不可交换性**：v2 是“先按药物对每个基因取中位数，再算 XSUM”，论文口径是“先对每个实例算 XSUM，再按药物取中位数”。两者数学上不可交换；L7b 已实测全局 Spearman 0.985–0.997，但中段排名可移动数千位。
7. **LOHO 的 k 依赖封顶**：`k=max(10, len(up)+len(down))`，封顶改变会改变 Jaccard。
8. **注释缺失不等于黄档**：见 5.4。
9. **WTCS 无显著性**：WTCS 只有 score，没有 p/FDR，不能做“显著药物”判断。
10. **药物名分组**：按 `pert_iname`/`cmap_name` 分组，盐型/别名可能被分开或合并；L7c 有专门讨论。

---

## 6. 外部注释（D4）

### 6.1 当前实现

【代码】`suitability.py:59-123`

- 路径：`GENE_ANNOTATIONS_PATH`，默认 `DATA_DIR/gene_annotations.tsv`（`config.py:66-68`）。
- 必需列：`gene`、`expressed_in_l1000_cells`、`tissue_specific`、`receptor_or_channel`。
- 布尔解析（`_parse_bool` 41-52）：`true/t/1/yes/y/是` → True；`false/f/0/no/n/否` → False；其他/空 → None（未知）。
- 文件不存在、读取失败、缺列、表中无该基因：返回 `annotation=None` + 中文 reason。
- 有缓存：按文件 mtime 缓存 DataFrame（`_ANNOTATION_CACHE` 38、80-88）。

### 6.2 缺失的实际影响

| 场景 | `annotation_used` | 第一层显示 | 档位 |
|---|---|---|---|
| 文件不存在 | false | “未提供生物学注释……第一层显示为‘未知’” | **不变** |
| 文件存在但缺列 | false | “缺少列……‘未知’” | **不变** |
| 文件存在但无该基因 | false | “注释表中没有……‘未知’” | **不变** |
| 文件正常 | true | 表达/组织/受体通道的实际判断 | 可能变红/降黄 |

v2 TP53 实测：`annotation_used=false`，`qc.reasons` 第一条是“未提供生物学注释（gene_annotations.tsv 未配置），第一层显示为“未知”，请研究者自行判断”，第二条才是黄档原因（`n_sig=43`、`LOHO=0.344`）。

**因此：部署报告第 4 节“TP53 yellow 因为 gene_annotations.tsv 未配置”的因果表述不准确。** 正确表述是：黄档由 `n_sig` 和 `LOHO` 决定；缺注释只影响第一层显示。该问题已记录在 `deliveries/docs-backend.md` 的“待人工确认/发现但未处理”。

### 6.3 建议的数据源与字段映射

> 以下是工程建议，不是已经采购/验证的许可证结论。上线前必须由人确认来源、版本、许可证和再分发范围。

| 字段 | 建议来源 | 派生方式 | 注意 |
|---|---|---|---|
| `expressed_in_l1000_cells` | LINCS `gene_info` + L1000 表达/检测统计；或 DepMap 表达 | 在 978 landmark 或全基因中是否有稳定表达 | 需要定义“表达”的阈值 |
| `tissue_specific` | Human Protein Atlas（HPA）tissue specificity / GTEx | `tissue_specific` 或 `tissue enriched` 映射为 true | HPA 版本要固定 |
| `receptor_or_channel` | HPA/UniProt 的 membrane/receptor/ion channel 注释；或 Repurposing Hub moa | 受体/通道/膜蛋白关键词 | Repurposing Hub 是 non-commercial，谨慎 |
| 疾病相关性/单倍剂量不足 | ClinGen gene-disease validity、gnomAD LOEUF | LOEUF 高分/单倍剂量不足基因可作为风险提示 | 这些不是当前四列的必需项，可作为附加列 |
| 必需基因 | DepMap CRISPR essentiality | 泛必需/选择性必需 | 用于解释“敲低后细胞死亡/签名失真” |

推荐存储：

```text
$CMAP_DATA_DIR/gene_annotations.tsv
# 或显式：
GENE_ANNOTATIONS_PATH=/home/keji/cmap_v2_data/gene_annotations.tsv
```

建议 schema（制表符分隔，首行表头）：

```text
gene	expressed_in_l1000_cells	tissue_specific	receptor_or_channel	source	version	notes
TP53	true	false	false	HPA+DepMap	2026-10	...
EGFR	true	false	true	HPA+UniProt	2026-10	...
```

许可证注意事项（均需人工复核，本文不做法律结论）：

- HPA：通常 CC BY 4.0，需保留 attribution；
- DepMap：通常 CC BY 4.0，需保留 attribution；
- ClinGen：CC BY 4.0（部分子数据集可能有额外条款）；
- gnomAD：有使用条款/attribution 要求，需阅读官网 terms；
- Repurposing Hub：文件头明确 “non-commercial use only”，与部分二手资料的 CC BY 4.0 说法冲突；**不要把原始文件或派生映射提交到公开仓库**，建议部署时本地生成（L7c 已记录）。
- 任何来源都要记录 `source`/`version`/`license`，不要把大文件提交进 git。

### 6.4 建议的验证

1. 用 10–20 个已知基因（TP53、EGFR、CDK4、TOP2A、MTOR、LMNA 等）人工核对四列；
2. 跑 `pytest backend/tests/test_suitability.py`；
3. 对 v2 TP53 重新计算签名，确认 `annotation_used=true` 且 `qc.reasons` 出现注释判断；
4. 确认注释缺失时 `grade` 不变（回归测试已覆盖）。

---

## 7. 修复历史索引（L0–L8）

【实测】git 图与合并提交：

| 任务 | 分支 | 提交 | 合并提交 | 日期 | 主要内容 |
|---|---|---|---|---|---|
| init | — | `315f965` | — | 2026-10-15 | 初始 backend + frontend + 参考文献 |
| L7 | `docs/L7-proposals` | `4867344` | `f3b4f10` | 2026-10-17 | 6 份设计文档（L7a–L7f），未实施 |
| L0 | `fix/L0-test-scaffold` | `aad1f6d` | `18685fe` | 2026-10-17 | 测试脚手架、FixtureProvider、夹具重建；暴露列序/BH/KS 符号问题 |
| L1 | `fix/L1-ks-sign` | `f23be5c` | `3b799ee` | 2026-10-18 | KS 符号、Bootstrap p、BH、XSUM 方向、n_sig/封顶/params |
| L6 | `fix/L6-hardening` | `ff7330c` | `c553da0` | 2026-10-18 | 任务去重、心跳超时、删除缓存鉴权、CORS 白名单、L3 启动失败 |
| L4 | `fix/L4-drug-null` | `2ce1bcb` | `4697806` | 2026-10-18 | 药物级随机签名 null、p/FDR/null_z、mode 排序 |
| L3 | `fix/L3-suitability` | `20b4611` | `f26413f` | 2026-10-18 | 适用性 precheck/LOHO/判档、mode、红档屏蔽 |
| L8 | `fix/L8-col-order` | `d4d3835`、`520086b` | `7cc2d7b` | 2026-10-18 | col/row 顺序修复脚本、哨兵、复核脚本；部署时修 v2 副本 |
| L2 | `fix/L2-cache-versioning` | `6f20f5c` | `8d367b6`（当时 HEAD） | 2026-10-18 | 参数哈希、ALGO_VERSION、文件锁、原子写 |

### 7.1 每个任务具体改了什么

- **L0**：`config.CACHE_DIR` 支持 `LMNA_CACHE_DIR`；`IDataProvider.get_all_shrna_samples`；`provider_factory`；`FixtureProvider`；`LMNA_TASK_INLINE`；测试脚手架。夹具来自 LINCS2020 beta Level5（约 24 MB，不入 git）。暴露了三个问题：列序错误、BH 前向 cummin 错误、KS 符号与论文相反。
- **L1**：KS 改为 `np.where(D_plus >= D_minus, D_plus, -D_minus)`；p 改 `(k+1)/(B+1)`；BH 删除前向 cummin；Bootstrap 排除目标列且无放回；`n_sig` 封顶前统计；每方向封顶 50；XSUM 改为 `score=-mimic`；API 增加 `n_sig/fast_mode/params`；`trt_sh.cgs` 排除。
- **L6**：任务去重（gene/method/fast-full/score_mode/params 哈希）；`submit_ex` 返回 `deduplicated`；running 心跳超时 7200s；启动清理残留；`DELETE /api/cache` 的 `X-Admin-Token`；CORS 白名单；`DATA_PROVIDER=l3` 启动即失败。
- **L4**：`drug_null` 随机签名 null；`p_mimic/p_reversal/fdr_mimic/fdr_reversal/null_z`；XSUM top/bottom 按 FDR+mode 排序；WTCS null 字段 None；`DRUG_NULL_N` 进入缓存键。
- **L3**：`suitability.py` 新增；`precheck`/`loho_jaccard_min`/`grade`/`load_annotation`；`/suitability` 路由；`/compute` 增加 mode 和 hairpin 422；`/signature` 增加 qc；`/drugs` 增加 mode/include_red/red_suppressed；红档屏蔽；gof 缓存。
- **L8**：`fix_col_names.py`（列序 + 可选行序）；`L5Provider` 的 `CHECK_COL_ORDER` 哨兵；`verify_drug_median.py`；测试夹具切片；部署时在 `~/cmap_v2_data` 执行 `--in-place --fix-rows`。
- **L2**：`signature_params_hash`（SHA1 10 位）；`ALGO_VERSION=2`；签名/药物/秩/中位数缓存全部版本化；`exclusive_file_lock`（fcntl/msvcrt）；`atomic_write_json`；`replace_file_with_retry`；任务 JSON 原子读写。
- **L7**：只出设计文档，未改代码。L7a 共享 landmark 层、L7b 实例级 XSUM、L7c 已上市药物、L7d 备选签名来源、L7e L3Provider、L7f SQLite 任务系统。

### 7.2 合并顺序

```text
315f965 init
  └─ f3b4f10  merge L7
      └─ 18685fe merge L0
          └─ 3b799ee merge L1
              └─ c553da0 merge L6
                  └─ 4697806 merge L4
                      └─ f26413f merge L3
                          └─ 7cc2d7b merge L8
                              └─ 8d367b6 merge L2
                                  └─ 4517e43 merge L5
                                      └─ 1850826 merge docs-backend（当前 origin/main）
```

### 7.3 尚未完成的任务

- **L5 前端**：已于 2026-10-18 完成并合并（`6812e33` → 合并提交 `4517e43`）；同源部署、适用性卡片、FDR 列、换肤、XSS 已落地。仍未完成的是“导出 / FDA 按钮”移植（v1 的 export/Figure3 未进 l5 版），属单独任务。
- **L3Provider**：`backend/l3_provider.py` 仍是 `NotImplementedError`；L7e 有设计文档。
- **L7a/L7b/L7c/L7d/L7f**：只有设计文档，未实施。

---

## 8. 重建 / 复核手册

> 红线：以下操作会删缓存/改数据文件/重启服务，必须由人在部署窗口执行。本文档本身不代替变更审批。

### 8.1 前置条件

- 已停止目标实例（至少停止 API，避免读到半截缓存）；
- 已确认代码版本（`git rev-parse --short HEAD` 或服务器文件 md5）；
- 已确认数据目录（v1: `/data2/wanggang/camp/...`；v2: `~/cmap_v2_data`）；
- 已备份 CSV/缓存（脚本会自动备份 CSV，但缓存删除不可恢复）；
- 已确认没有别的进程在读同一缓存目录（v1/v2 缓存目录不同，不要混用）。

### 8.2 数据层修复（L8）

#### 只检查

```bash
cd ~/lmna_v2   # 或任何含 scripts/ 的部署目录
python scripts/fix_col_names.py --check --data-dir ~/cmap_v2_data
```

期望：

```text
col_sig_ids.csv: 473647 行，GCTX 元数据 473647 行
  同位置一致: 473647/473647；集合相同: True
  [OK] 顺序一致
row_gene_ids.csv: 12328 行，GCTX 元数据 12328 行
  同位置一致: 12328/12328；集合相同: True
  [OK] 顺序一致
```

#### 原地修复列序 + 行序

```bash
python scripts/fix_col_names.py --data-dir ~/cmap_v2_data --in-place --fix-rows
```

- 自动备份 `col_sig_ids.csv.bak-<timestamp>`、`row_gene_ids.csv.bak-<timestamp>`；
- 原子写；
- 若 GCTX 有重复 id 会直接退出；
- 抽样校验失败会退出，不会写文件。

#### 只修列序（不推荐）

```bash
python scripts/fix_col_names.py --data-dir ~/cmap_v2_data --in-place
```

不修行序时，`get_expression_matrix` 的 978 维向量仍会取错基因；L8 交付已明确“只修列序时验收 1/3/4 不成立”。

#### 共享目录

如果决定也修 `~/cmap/cmap_data`（会影响老 cmap/v1 L5 路径），必须先协调停 cmap/LMNA，并确认备份：

```bash
python scripts/fix_col_names.py --check --data-dir ~/cmap/cmap_data
python scripts/fix_col_names.py --data-dir ~/cmap/cmap_data --in-place --fix-rows
```

修完后 cmap 需要重启/重建内存索引。

### 8.3 缓存删除矩阵

不同任务的删除范围（以 `$CACHE_DIR` 为目标）：

| 任务 | 必须删除 | 原因 |
|---|---|---|
| L1（KS/BH/符号） | `signatures/`、`drug_scores/`、`tasks/`、`_shrna_rank_matrix*`、`_drug_median_matrix*`、`_drug_names*` | 旧签名/药物/秩/中位数全部口径变化 |
| L2（版本化） | 同上；版本化会兜底，但建议清 | 避免旧无哈希文件占空间/混淆 |
| L3（判档） | `signatures/`、`drug_scores/`、`tasks/` | 旧签名没有 qc；红档屏蔽依赖 qc |
| L4（药物 null） | `drug_scores/`、`tasks/` | 旧药物结果没有 p/FDR/null_z |
| L8（列/行序） | `signatures/`、`drug_scores/`、`tasks/`、`_drug_median_matrix*`、`_drug_names*` | 旧缓存由错误映射生成 |
| 只换 CPU/不动算法 | 不需要 | — |

L2 交付给出的通用删除命令：

```bash
cd ~/lmna_v2   # 或目标实例根目录
CACHE=~/lmna_v2_cache
rm -rf "$CACHE/signatures" "$CACHE/drug_scores" "$CACHE/tasks"
rm -f  "$CACHE"/_shrna_rank_matrix* "$CACHE"/_shrna_rank_shape*
rm -f  "$CACHE"/_drug_median_matrix* "$CACHE"/_drug_names*
rm -f  "$CACHE"/*.lock
```

注意：`_shrna_rank_matrix*` 会匹配 `.dat`、`.shape.txt`、`.lock`；`_drug_median_matrix*` 会匹配 `.npy`、`.lock`；`_drug_names*` 会匹配 `.csv`。删除前先 `ls` 确认。

v1 的缓存目录是 `~/lmna_app/LMNA/cache`，文件名没有版本号；如果要重建 v1，删除：

```bash
cd ~/lmna_app/LMNA
rm -rf cache/signatures cache/drug_scores cache/tasks
rm -f  cache/_l4zsvc_shrna_z.dat cache/_l4zsvc_shrna_z.meta.json
rm -f  cache/_l4zsvc_shrna_rank_matrix.dat cache/_l4zsvc_shrna_rank_shape.txt
rm -f  cache/_fda_instance_matrix_*.npy cache/_fda_instance_meta_*.csv
rm -f  cache/_fda_masked_matrix_*.npy
rm -f  cache/_xsum_null_*.npy cache/_xsum_null_*_drugs.csv
```

v1 重建代价很高（`zsvc_build.py` 全量重建约 1 分钟日志时间，但实际 I/O 受缓存影响；`_fda_instance_matrix` 从 89 GB GCTX 读 235,433 列，耗时更长）。非必要不要重建 v1。

### 8.4 重建步骤（v2）

1. 停 v2：

```bash
bash ~/lmna_v2/stop_frontend_v2.sh
bash ~/lmna_v2/stop_v2.sh
```

2. 确认 8004/8084 释放：

```bash
ss -tln | grep -E ':8004|:8084' || true
```

3. 删缓存（按 8.3 的范围）。
4. 确认数据 CSV 正确（8.2 的 `--check`）。
5. 启动：

```bash
bash ~/lmna_v2/start_v2.sh
bash ~/lmna_v2/start_frontend_v2.sh
```

6. 健康检查：

```bash
curl -sk https://127.0.0.1:8004/api/health
```

7. 首次计算（以 TP53 为例）：

```bash
curl -sk -X POST https://127.0.0.1:8004/api/genes/TP53/compute \
  -H 'Content-Type: application/json' \
  -d '{"method":"xsum","mode":"lof"}'
```

8. 轮询任务：

```bash
curl -sk https://127.0.0.1:8004/api/tasks/<task_id>
```

9. 验证签名/药物：

```bash
curl -sk https://127.0.0.1:8004/api/genes/TP53/signature
curl -sk 'https://127.0.0.1:8004/api/genes/TP53/drugs?method=xsum&mode=lof&top_n=3'
```

预期（2026-10-18 部署实测，仅作趋势参考，不保证每次数值完全相同）：

```text
n_samples=71, n_hairpins=7, n_cells=12
n_sig=43（up 19 / down 24）
LOHO=0.34375, grade=yellow
target_ks=-0.5921, target_median_z=-2.9226
drug all_scores=19,811, null M=10000, top BRD-K59550348 score=24.8246
```

### 8.5 药物中位数复核（`verify_drug_median.py`）

脚本：`scripts/verify_drug_median.py`（276 行）。

参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--data-dir` | `~/cmap/cmap_data` | 真值 GCTX/基因信息/sig_info 所在目录 |
| `--cache-dir` | `~/LMNA/cache` | 缓存目录 |
| `--truth-gctx` | data-dir 下的 GSE92742 Level5 | 真值 GCTX |
| `--n-drugs` | 5 | 抽样药物数 |
| `--drug` | 无 | 只复核指定药物 |
| `--max-sigs-per-drug` | 200 | 每药最多抽样 signature 数；0=全部 |
| `--seed` | 42 | 抽样种子 |
| `--min-corr` | 0.99 | 低于阈值退出码 1 |
| `--beta-dir` | 无 | 可选 LINCS2020 beta Level5，仅趋势对照 |

**已知限制**：脚本硬编码读取未版本化文件名 `_drug_median_matrix.npy` / `_drug_names.csv`（`verify_drug_median.py:42-43`），不会自动找 `.v2` 文件。v2 部署时是用 `~/lmna_v2_verify` 软链接绕过：

```bash
mkdir -p ~/lmna_v2_verify
ln -sf ~/lmna_v2_cache/_drug_median_matrix.v2.npy ~/lmna_v2_verify/_drug_median_matrix.npy
ln -sf ~/lmna_v2_cache/_drug_names.v2.csv ~/lmna_v2_verify/_drug_names.csv

python scripts/verify_drug_median.py \
  --data-dir ~/cmap_v2_data \
  --cache-dir ~/lmna_v2_verify \
  --n-drugs 5
```

期望：

```text
[verify] 行序诊断: row_gene_ids.csv vs GCTX ROW 同位置一致 12328/12328
[verify] [OK] 全部药物 r >= 0.99
```

如果行序诊断显示 `[FAIL]`，说明 `--fix-rows` 没执行，缓存不可信；先修数据再重建。

### 8.6 签名/任务复核

```bash
# 任务列表
curl -sk 'https://127.0.0.1:8004/api/tasks?limit=5'

# 单个任务
curl -sk https://127.0.0.1:8004/api/tasks/<task_id>

# 适用性
curl -sk https://127.0.0.1:8004/api/genes/TP53/suitability
```

检查点：

- `status=completed`；
- `signature.n_sig > 0`；
- `qc.grade` 与 `n_sig`/`LOHO` 一致；
- 红档时 `/drugs` 默认空列表，`include_red=true` 非空；
- `params` 里的 `FDR_THRESHOLD`/`BOOTSTRAP_N` 与部署脚本一致；
- 任务 JSON 的 `params_hash` 与签名缓存文件名中的 `h` 一致。

### 8.7 测试套件

本地（Windows，fixture 在 `D:\agent-workspace\deliveries\task-L0\fixtures`）：

```bash
cd backend
LMNA_FIXTURE_DIR='D:\agent-workspace\deliveries\task-L0\fixtures' \
  D:/mine_Anaconda3/python.exe -m pytest -q
```

2026-10-18 实测：

```text
128 passed, 1 skipped, 6 warnings in 34.22s
```

- 1 skipped 是 Table S1 相关（缺少 `backend/tests/fixtures/table_s1.tsv`），不是失败；
- 6 warnings 是 starlette `multipart` 和 httpx `app` 的弃用提示。

服务器上跑测试需要 cmap conda 环境和夹具；生产数据目录不要直接跑会写缓存的测试，除非显式设置 `LMNA_CACHE_DIR` 到临时目录。

### 8.8 回滚检查清单

- [ ] 停止 v2（`stop_frontend_v2.sh` + `stop_v2.sh`）；
- [ ] 确认 8004/8084 释放；
- [ ] 如需恢复缓存，使用备份/重建，不要从 v1 复制（口径不同）；
- [ ] 如需删除 v2，确认不删共享数据；
- [ ] 恢复 v1 不受影响（v1 独立目录、独立缓存、独立端口）；
- [ ] 记录变更时间、操作人、commit、数据目录、缓存版本。

---

## 9. 已知问题与维护清单

| # | 问题 | 证据 | 影响 | 建议 |
|---|---|---|---|---|
| 1 | 部署报告说 TP53 黄档“因为 gene_annotations.tsv 未配置” | 【实测】qc.reasons 两条；代码 306-312 只加 reason | 误导排障/验收 | 改为“黄档由 n_sig/LOHO 决定；缺注释只影响第一层显示” |
| 2 | `verify_drug_median.py` 只读未版本化缓存名 | 【代码】42-43 | v2 直接跑会找不到文件 | 传 `--cache-dir ~/lmna_v2_verify` 软链接；后续改成按 ALGO_VERSION 查找 |
| 3 | 导出 / FDA 按钮未移植 | 【代码】l5 版无 export/Figure3，v1 有 | 新前端缺这两类入口 | 属单独的 v1→l5 移植任务；L5 本波已明确不做 |
| 4 | 共享 `~/cmap/cmap_data` 未修列/行序 | 【实测】md5/首行 | 老 cmap 和 v1 L5 路径仍读错 | 协调停服后执行 `--in-place --fix-rows`，并重建 cmap 索引 |
| 5 | `deliveries/task-L7.md` / `docs/design/L7e-l3-provider.md` 称“服务器只有 Level5” | 【实测】`/data2/wanggang/camp/level3|4` 存在且 v1 在用 | 设计文档的数据前提过时，可能重复下载数十 GB | 更新 L7e 的数据可用性描述 |
| 6 | v1 CORS `*` + credentials | 【代码】v1 main.py CORS | 浏览器安全策略/安全风险 | v1 只在内网；新代码已改白名单 |
| 7 | v1 `DELETE /api/cache` 无鉴权 | 【代码】v1 main.py:279-287 | 任意人可删缓存 | v1 保持现状或加反代限制；v2 已有 token |
| 8 | v2 不在 systemd | 【实测】无 lmna unit | 服务器重启后需手工启动 | 评估加入 portal-stack 或独立 unit（不影响老服务） |
| 9 | `DrugQueryRequest` 死代码 | 【代码】main.py:78-83 | 改错模型不生效 | 删除或改为 `/drugs` 的依赖模型 |
| 10 | WTCS 无 p/FDR | 【代码】drug_scorer.py:293-343 | 不能做显著性判断 | UI 明确标注“仅 score”；需要显著性时用 XSUM |
| 11 | 药物 `all_scores` 大 JSON | 【实测】5.2 MB/任务 | 缓存膨胀、任务结果不返回 | L7f 建议移 NPZ；短期可接受 |
| 12 | 任务去重是进程内锁 | 【代码】task_queue.py:314 | 多进程 worker 会重复 | 单 worker 部署；扩展时用文件锁/DB |
| 13 | pending 任务无超时 | 【代码】task_queue.py:242-277 | 死 pending 会挡住去重 | 启动清理可回收；可加 pending TTL |
| 14 | 旧签名缓存无 qc | 【代码】main.py:236；L3 交付 | 红档屏蔽不生效 | 部署后删 `signatures/` 重算 |
| 15 | 旧药物缓存无 p/FDR | 【代码】drug_scorer.py:345-359 | `/drugs` 字段缺失/None | 删 `drug_scores/` 重算 |
| 16 | `DRUG_NULL_N=10000` 的 FDR 分辨率 | 【实测】fdr min 0.990451 | 显著药物 FDR 仍接近 1 | 提高 M 或限制检验族（见 5.7） |
| 17 | `SUITABILITY_MIN_HAIRPINS=2` 直接拒绝 | 【代码】main.py:161-170 | 1 hairpin 基因无法计算 | 产品确认是否允许“仅预检/不判药” |
| 18 | v1/v2 论文模式不同步风险 | 【实测】两个 start 脚本都覆盖；config 默认不同 | 误以为默认 0.05 | 文档/启动脚本/健康检查里显式打印参数 |
| 19 | `target_median_z` 只对 landmark 有值 | 【代码】signature_engine.py:263-268 | 非 landmark 靶点为 null | UI 标注“非 landmark” |
| 20 | cmap/v1 共用共享数据但版本不同 | 【实测】共享 CSV 旧、v2 CSV 新 | 同一台机器两种语义 | 明确每个实例的 `CMAP_DATA_DIR`，不要共用可变 CSV |

---

## 10. 附录

### 10.1 术语

| 术语 | 含义 |
|---|---|
| L1000 / LINCS | NIH LINCS L1000 数据集；978 个 landmark 基因 |
| GCTX | LINCS 的 HDF5 矩阵格式；`0/META/COL/id` 是列 id，`0/META/ROW/id` 是行 id |
| MODZ / ZSPCINF | Level5 / Level4 的 z-score 数据层级 |
| ZSVC | 按同板 `ctl_vector` 对照重建的 z-score（v1 生产 sh 侧） |
| KS | 带符号 Kolmogorov–Smirnov 统计量；v2 的签名核心 |
| ES_up/ES_down | v1 的 GSEA 式单侧富集分数 |
| BH | Benjamini–Hochberg FDR 校正 |
| LOHO | Leave-One-Hairpin-Out；留一 hairpin 稳定性 |
| Jaccard | 两个基因集合的交集/并集 |
| XSUM | 签名基因 z 值求和打分 |
| WTCS | 加权连接分数 |
| lof / gof | loss-of-function（找逆转药）/ gain-of-function（找模拟药） |
| D1/D2/D3/D4 | 项目决策编号；D1=阈值/公告，D2=CORS，D3=样本门槛，D4=外部注释 |

### 10.2 常用只读检查命令

```bash
# 健康
curl -sk https://127.0.0.1:8003/api/health
curl -sk https://127.0.0.1:8004/api/health

# 端口
ss -tln | grep -E ':8003|:8004|:8083|:8084'

# 进程
ps -eo pid,ppid,lstart,cmd | grep -E 'lmna_app/LMNA|lmna_v2|uvicorn' | grep -v grep

# v2 日志
tail -50 ~/lmna_v2/server_v2.log
tail -50 ~/lmna_v2/frontend_v2.log

# 缓存
ls -lh ~/lmna_v2_cache
ls -lh ~/lmna_v2_cache/signatures ~/lmna_v2_cache/drug_scores

# 数据 CSV 行数
wc -l ~/cmap_v2_data/col_sig_ids.csv ~/cmap_v2_data/row_gene_ids.csv

# GCTX 元数据（只读）
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cmap
python - <<'PY'
import h5py
p='/home/keji/cmap_v2_data/GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx'
with h5py.File(p,'r') as f:
    print(len(f['0/META/COL/id']), len(f['0/META/ROW/id']), f['0/DATA/0/matrix'].shape)
PY
```

### 10.3 文档维护检查清单

- [ ] 新增/修改 API 字段 → 更新 2.3、2.4、delivery；
- [ ] 改缓存文件名/哈希参数 → 更新 2.6、3.4；
- [ ] 改统计口径/阈值 → 更新第 5 章、`signature_params` 说明；
- [ ] 改部署端口/路径/脚本 → 更新第 1 章；
- [ ] 改数据源/列序 → 更新第 3、8 章；
- [ ] 新增修复任务 → 更新第 7 章；
- [ ] 新增已知问题 → 更新第 9 章；
- [ ] 每次发布前跑 8.7 的测试，并把结果写进 delivery。

---

*本文只描述现状，不构成部署授权。所有删除缓存、替换数据文件、重启服务的操作都必须按变更流程由人执行。*

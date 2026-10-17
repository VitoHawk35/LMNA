# docs-backend 交付说明

- 任务：子 agent 3 · LMNA 后端现状文档
- 分支：`fix/docs-backend`
- 基线：`origin/main` @ `8d367b6`
- 产物：
  - `docs/BACKEND_SITUATION.md`（中文正文，英文文件名，随仓库长期维护）
  - `deliveries/docs-backend.md`（本文件）
- 工作树：`D:\agent-workspace\worktrees\task-DOC`
- 核对日期：2026-10-18
- 服务器：`ssh -i ~/.ssh/lmna_deploy keji@10.39.15.238`，**全程只读**

> 只读声明：本次没有修改服务器代码/数据/缓存，没有删除缓存，没有重启服务，没有安装依赖，没有 scp 证书或密钥。所有写操作只发生在本地 worktree 的两个 Markdown 文件。

---

## 1. 交付物结构

`docs/BACKEND_SITUATION.md` 共 10 章：

1. 版本与部署拓扑（GitHub main / v1 / v2、端口、目录、PID/日志、启停、回滚、差异表）
2. 后端架构与模块清单（入口、单例、14 个模块、全部 API 字段、任务 JSON、配置总表）
3. 数据层全景（`fast_matrix.npy`/GCTX/两个 CSV、L8 列序+行序 bug、缓存文件与版本化、v2 缓存实测）
4. v1 现状（文件清单、数据源、路由、前端按钮映射、统计口径、缓存、实测、与 l5 的差异）
5. 统计方法与已知局限（带符号 KS、Bootstrap、BH、LOHO、判档、XSUM/WTCS、药物 null、`DRUG_NULL_N=10000` 的 FDR 分辨率、D1 双模式）
6. 外部注释 D4（当前实现、缺失影响、建议数据源/字段/许可证/验证）
7. 修复历史索引 L0–L8（每个任务改了什么、合并提交、未完成任务）
8. 重建/复核手册（`fix_col_names.py`、`verify_drug_median.py` 的真实参数与用法、缓存删除矩阵、重建步骤、测试）
9. 已知问题与维护清单（20 项）
10. 附录（术语、只读检查命令、文档维护检查清单）

doc 中的路径、端口、字段名、文件名、行号均按 `8d367b6` 或服务器实际文件核对。

---

## 2. 实际读取的来源

### 2.1 仓库代码（worktree `D:\agent-workspace\worktrees\task-DOC`）

逐文件阅读：

```text
backend/main.py
backend/config.py
backend/data_provider.py
backend/provider_factory.py
backend/l5_provider.py
backend/l3_provider.py
backend/fixture_provider.py
backend/signature_engine.py
backend/suitability.py
backend/drug_median_cache.py
backend/drug_scorer.py
backend/cache_manager.py
backend/task_queue.py
backend/tests/（16 个文件，含 conftest、make_fixture、L2/L8/API/任务/统计/判档测试）
frontend/index.html
scripts/fix_col_names.py
scripts/verify_drug_median.py
deliveries/task-L0.md
deliveries/task-L1.md
deliveries/task-L2.md
deliveries/task-L3.md
deliveries/task-L4.md
deliveries/task-L6.md
deliveries/task-L8.md
deliveries/task-L7.md
docs/design/L7a–L7f（用于确认“设计未实施”）
```

另外读取：

```text
D:\agent-workspace\README.md
D:\agent-workspace\deliveries\deploy\部署完成报告-2026-10-18.md
```

### 2.2 服务器（只读）

v1 `~/lmna_app/LMNA`：

```text
backend/main.py, config.py, l4zsvc_provider.py, l4_provider.py,
l3_provider.py, l5_provider.py, signature_engine.py, drug_scorer.py,
task_queue.py, cache_manager.py, export_store.py, figure3_replica.py,
check_status.py, chatgpt_template.py
frontend/index.html
start.sh, stop.sh, status.sh, start_server.sh
cache/ 文件清单、大小、signature/drug_scores 内容
processes、ports、health、frontend HTTP 200
```

v2 `~/lmna_v2`：

```text
backend/*.py 全量 md5（与 8d367b6 逐文件一致）
frontend/index.html 的 API_BASE
start_v2.sh, stop_v2.sh, start_frontend_v2.sh, stop_frontend_v2.sh,
serve_frontend_v2.py（只读）
server_v2.log
cache/ 文件清单、大小、numpy 形状
health / genes / status / suitability / task / drugs 实测
processes、ports
```

数据：

```text
~/cmap/cmap_data/       文件大小、md5、CSV 首行/行数
~/cmap_v2_data/         软链接、CSV 行数/md5/首末行、备份文件
~/lmna_v2_verify/       软链接目标
GCTX 0/META/COL/id、0/META/ROW/id、0/DATA/0/matrix shape（h5py 只读）
```

v1 深层数据/日志：

```text
/data2/wanggang/camp/level3、level4、level5 目录存在性与文件大小
v1 signature_engine.py / drug_scorer.py / l4zsvc_provider.py / l4_provider.py
v1 analysis/zsvc_build.py 与 zsvc_build.log
v1 缓存 npy 文件头/形状/内容抽样
```

### 2.3 git 历史

```text
git log --graph --all --decorate --oneline
git show --stat / --name-status（L0–L8）
git branch -a、git rev-parse
```

确认合并链：

```text
315f965 init
  → f3b4f10 L7
  → 18685fe L0
  → 3b799ee L1
  → c553da0 L6
  → 4697806 L4
  → f26413f L3
  → 7cc2d7b L8
  → 8d367b6 L2（origin/main）
```

`fix/L5-frontend` 在核对时与 `8d367b6` 同点，无独立提交。

### 2.4 测试

本地运行（fixture 来自 L0 交付）：

```bash
cd backend
LMNA_FIXTURE_DIR='D:\agent-workspace\deliveries\task-L0\fixtures' \
  D:/mine_Anaconda3/python.exe -m pytest -q
```

结果：

```text
128 passed, 1 skipped, 6 warnings in 34.22s
```

- skip 是既有 Table S1 相关，不是失败；
- warnings 是 starlette `multipart` 与 httpx `app` 的弃用提示。

---

## 3. 证据分级：哪些是实测，哪些只是推断

`docs/BACKEND_SITUATION.md` 正文逐条带标记。这里汇总：

### 3.1 已读代码确认（【代码】）

- 所有 API 路由、请求/响应字段、默认值、校验顺序、状态码；
- `config.py` 的全部参数与 `signature_params()` 组成；
- `L5Provider` 的列/行映射、978 landmark 选取、`trt_sh`/`trt_cp` 过滤；
- v2 带符号 KS 公式、双侧经验 p、BH、FDR+KS 筛选、封顶与 `n_sig` 顺序；
- Bootstrap 无放回 + 排除目标列；
- LOHO 的 `k=max(10, len(up)+len(down))` 与 Jaccard 最小值；
- 红/黄/绿判档顺序，以及“缺注释只加 reason、不改档位”；
- XSUM `mimic=Σup−Σdown`、`score=−mimic`、`lof/gof` 排序；
- 药物 null 的 `M=DRUG_NULL_N`、`batch=500`、`seed=42`、p 平滑、两方向分别 BH；
- WTCS 的 p/FDR/null_z 全为 None；
- 缓存文件名规则、参数哈希、`ALGO_VERSION`、锁、原子写、回退查找；
- 任务去重键、`max_workers=2`、running 心跳超时、启动清理；
- 删除缓存需要 `X-Admin-Token`，token 未配置时 403；
- `DrugQueryRequest` 是死代码；
- v1 的 GSEA 式 ES、Bootstrap 有放回/不排除目标列、up/down 各自 BH、XSUM 掩码/置换 p、FDA 过滤、export/figure3 路由；
- v1 的 `allow_origins=["*"]` + credentials、DELETE 无鉴权；
- `fix_col_names.py`、`verify_drug_median.py` 的参数与限制（脚本源码逐行阅读）。

### 3.2 服务器只读实测（【实测】）

- v1/v2 端口、进程、PID、日志、health；
- v2 后端 13 个 `.py` 与 `8d367b6` md5 完全一致；
- v2 前端 `API_BASE` 被改为 `https://10.39.15.238:8004`；
- v2 TP53：71 样本、7 hairpin、12 细胞系、`n_sig=43`（19 up/24 down）、LOHO 0.34375、yellow、`target_ks=-0.5921109478959647`、`target_median_z=-2.922600030899048`；
- v2 药物：19,811 个 `all_scores`、null M=10000、top `BRD-K59550348` score 24.8246、`p_reversal=0.0004`、`fdr_reversal=0.990451`、`null_z=-3.4347`；
- `p_reversal` 落在下限 9.999e-5 的药物有 2 个，`fdr_reversal` 最小 0.9904509549；
- v2 缓存文件形状：`_drug_median_matrix.v2.npy (978,19811)`、`_shrna_rank_matrix.v2.154993.dat (978,154993)`；
- v2 `server_v2.log`：任务 01:47:26 创建、01:53:29 完成（约 6 分钟）；
- v1 health：`provider=l4zsvc`、`available_genes=4435`、`cached_signatures=2`；
- v1 LMNA 签名：84 样本、53 up/20 down、Bootstrap 100000、无 qc；
- v1 药物：651 个、top tramadol score -8.8995 p 0.00029997；
- 共享 `~/cmap/cmap_data` 与 v2 `~/cmap_v2_data` 的 CSV md5/首行/行数；
- 共享目录 CSV 仍是旧顺序，v2 副本已修正并有 `.bak-20261018-014410`；
- `~/lmna_v2_verify` 的软链接指向 v2 缓存；
- `fix/L5-frontend` 与 `main` 同点；
- 128 passed / 1 skipped。

### 3.3 日志/报告确认（【日志/报告】）

- L8 部署验证：列 473647/473647、行 12328/12328、抽样 max|diff|=0、药物中位数 r≥0.99；
- L0 fixture 来源、24 MB 大小、978×3553 sh / 978×3155 cp；
- L1 fixture 回归值 CDK4 −0.7457、TOP2A −0.8374、EGFR −0.5282；
- v1 `zsvc_build.log` 的池大小、对照孔、板数、FDA 药物数、构建时间；
- 部署报告的启停命令、PID/日志路径、回滚命令、已知差异；
- 部署报告“TP53 yellow 因为 gene_annotations.tsv 未配置”的原文（该因果表述被实测推翻，见第 6 节）。

### 3.4 仅从代码/文档推断，未实测（【推断】）

| # | 推断项 | 依据 | 风险 | 建议复核方式 |
|---|---|---|---|---|
| 1 | v1 `export_store` 的 TTL/一次性下载行为 | 只读 `export_store.py`，未实际 POST/GET 导出 | 低（不影响主流程） | 在 v1 上对测试基因执行一次 ZIP 导出，确认 token 失效时间 |
| 2 | v1 Figure3 A/B/C 三张图的完整渲染 | 只读 `figure3_replica.py` 与路由，未打开图片 | 中（如果文档要承诺该功能可用） | 浏览器打开 `/api/genes/LMNA/figure3`，人工看三面板 |
| 3 | v1 “Touchstone”的业务含义 | 只看到 `trt_sh_isgold.csv` 与前端列名，未核对数据字典 | 中（容易被误解为 FDA 按钮） | 查论文/数据说明，确认 touchstone 定义 |
| 4 | v1 `L4ZSVCProvider` 药物侧“official L4” | docstring 声明，未逐值对照 L4 GCTX | 低 | 抽样药物中位数与 L4 GCTX 复核 |
| 5 | 修共享 CSV 后 cmap 的 C1/C3/C4/C5 结果变化 | L8 交付的代码定位，未在 cmap 上实测 | 高（影响老 cmap） | 停 cmap 后修 CSV、重启，跑固定查询对比修复前后 |
| 6 | `--fix-rows` 对 cmap 行映射的修复效果 | 代码路径推断，未实测 | 高 | 同上，用已知 gene_id 查询验证 |
| 7 | v1 HTTPS 前端 `ssl.wrap_socket` 的具体协议版本 | 只读脚本，未做 TLS 握手分析 | 低 | `openssl s_client -connect` 只读检查 |
| 8 | `DRUG_NULL_N=1e6` 的实际耗时/内存 | 按分批实现线性外推，未跑 1e6 | 中（影响部署窗口） | 在 v2 缓存副本上单独 benchmark，不写生产缓存 |
| 9 | v2 `gof` 模式的药物排名业务合理性 | 只验证排序代码，未做生物学复核 | 中 | 用已知 agonist/antagonist 基因对做阳性对照 |
| 10 | pending 任务长期堆积的实际概率 | 只读代码，未压测 | 低 | 压测/观察任务目录 |
| 11 | `LMNA_CORS_ORIGINS` 非法格式的启动行为 | 只读解析代码，未注入非法值 | 低 | 测试环境设非法值启动 |
| 12 | v1 `p_value` 只对 `obs<0` 计算的实际影响 | 只读 `drug_scorer.py`，未统计全药物 | 中 | 统计 v1 缓存中 score>=0 的药物数量 |
| 13 | v1 `_fda_instance_matrix` 重建耗时 | 只知道文件大小和 GCTX 89 GB，未实测 | 中 | 在维护窗口计时 |
| 14 | `.bak-*` 文件不会被运行时读取 | 代码只读固定文件名，推断 | 低 | `lsof`/grep 确认 |
| 15 | v2 前端表格在真实浏览器中的渲染 | 只读 HTML，未点击 | 低 | 浏览器回归 |

**未做的实测**（受只读红线限制，明确说明）：

- 没有运行 `fix_col_names.py` 对生产数据写文件；
- 没有运行 `verify_drug_median.py` 的生产全量复核（只读源码和已部署结果）；
- 没有触发 v1 的 export/figure3；
- 没有修改/重启任何服务；
- 没有安装 `h5py`（服务器 cmap 环境已有，只读使用）。

---

## 4. 需要人工确认（🧑‍⚖️）

1. **药物 FDR 方案**：把 `DRUG_NULL_N` 提到 1e6，还是限制 BH 检验族（如只对已上市/候选药物）？两者统计口径不同。提高 M 是工程可做的，限制族必须由统计/产品负责人拍板。
2. **共享 `~/cmap/cmap_data` 是否修复**：修复会影响老 cmap 和 v1 的 L5 路径，需要停服窗口；不修则“v2 正确、cmap 仍旧错”长期并存。
3. **D4 注释数据源与许可证**：HPA/DepMap/ClinGen/gnomAD/Repurposing Hub 的版本、许可证、再分发范围，必须由人确认；尤其 Repurposing Hub 的 non-commercial 条款。
4. **v2 是否纳入 systemd/portal-stack**：目前重启后必须手工启动；是否加入自启、是否影响老服务，需要运维决策。
5. **v1 的去留**：v1 继续维护还是冻结？如果冻结，是否还需要保证旧结果可复现（旧缓存/旧算法）？
6. **v2 部署参数是否保持论文模式**：`FDR=0.001`、`BOOTSTRAP=100000` 是部署脚本覆盖值；是否长期保持，还是切回代码默认 0.05/1000？
7. **1 hairpin 基因是否允许计算**：当前 `SUITABILITY_MIN_HAIRPINS=2` 直接 422；产品上是否允许“只预检、不出药”？
8. **红档是否默认屏蔽药物**：当前默认屏蔽，`include_red=true` 才返回；是否所有场景都合适？
9. **WTCS 是否需要显著性**：当前 WTCS 无 p/FDR；如果要加，需要新的 null 方案，不能复用 XSUM 的。
10. **部署报告更正**：TP53 黄档的因果表述由谁改、是否发更正说明。
11. **L7e 文档更新**：`deliveries/task-L7.md` 与 `docs/design/L7e-l3-provider.md` 称“服务器只有 Level5”，与 `/data2` 实际不符，需文档 owner 更新。
12. **前端 API_BASE/同源策略**：正式前端是用同源反向代理，还是保留绝对地址；这决定 L5 前端的部署方式。
13. **`DrugQueryRequest` 死代码**：删除还是改成 `/drugs` 的依赖模型。
14. **v1 CORS/DELETE 鉴权**：v1 是否加反代限制，还是接受内网现状。

---

## 5. 发现但未处理的问题

> 这些是本次调查发现、但没有代码改动权限/未在任务范围内修复的问题。按严重度粗排。

| # | 问题 | 证据 | 影响 | 建议 |
|---|---|---|---|---|
| 1 | 共享 `~/cmap/cmap_data` 的 `col_sig_ids.csv`/`row_gene_ids.csv` 仍是旧顺序 | 【实测】md5/首行 | 老 cmap 和 v1 L5 路径继续读错 | 停服后 `--in-place --fix-rows`，重启 cmap |
| 2 | `verify_drug_median.py` 硬编码未版本化缓存名 | 【代码】`verify_drug_median.py:42-43` | v2 直接跑找不到文件，部署时靠软链接绕过 | 改成按 `ALGO_VERSION` 查找，或加 `--algo-version` |
| 3 | L5 前端未提交；v2 前端仍是旧 UI | 【实测】`fix/L5-frontend`=8d367b6；v2 HTML 无 qc/FDR | 用户看不到适用性/FDR/红档；API 字段被浪费 | 独立前端任务；先解决 API_BASE/同源 |
| 4 | 部署报告把 TP53 黄档归因于缺注释 | 【实测】qc.reasons 两条；代码 306-312 | 排障时误判为“配注释就能变绿” | 更正为“n_sig=43 + LOHO=0.344 决定黄档” |
| 5 | `task-L7.md` / `L7e-l3-provider.md` 称服务器只有 Level5 | 【实测】`/data2/wanggang/camp/level3|4` 存在且 v1 在用 | 可能重复下载数十 GB 数据 | 更新 L7e 的数据可用性 |
| 6 | v1 CORS `*` + credentials | 【代码】v1 main.py CORS | 浏览器规范下 credentials 与 wildcard 不兼容；安全面过大 | v1 加反代/白名单；v2 已修 |
| 7 | v1 `DELETE /api/cache` 无鉴权 | 【代码】v1 main.py:279-287 | 任意人可删缓存 | 反代限制或加 token |
| 8 | v2 无 systemd 自启 | 【实测】无 lmna unit | 重启后服务不自恢复 | 评估 portal-stack/独立 unit |
| 9 | `DrugQueryRequest` 死代码 | 【代码】main.py:78-83 | 改模型不生效 | 删除或接线 |
| 10 | WTCS 无 p/FDR/null_z | 【代码】drug_scorer.py:293-343 | 不能做显著性判断 | UI 标注“仅 score” |
| 11 | `all_scores` 19,811 条写 JSON（5.2 MB/任务） | 【实测】 | 缓存膨胀；任务结果不返回 | L7f 的 NPZ 方案，未实施 |
| 12 | 任务去重是进程内 `threading.Lock` | 【代码】task_queue.py:314 | 多进程部署会重复计算 | 单 worker；扩展时文件锁/DB |
| 13 | pending 任务无超时 | 【代码】task_queue.py:242-277 | 死 pending 会挡住同键去重 | 启动清理可回收；可加 pending TTL |
| 14 | 旧签名缓存没有 qc | 【代码】main.py:236；L3 交付 | 红档屏蔽不生效 | 部署后删 `signatures/` 重算 |
| 15 | 旧药物缓存没有 p/FDR | 【代码】drug_scorer.py:345-359 | `/drugs` 字段缺失/None | 删 `drug_scores/` 重算 |
| 16 | `DRUG_NULL_N=10000` 的 FDR 分辨率 | 【实测】fdr min 0.990451 | 显著药物 FDR 仍接近 1，容易被误判为失败 | 提高 M 或限制族（见 🧑‍⚖️ 1） |
| 17 | `SUITABILITY_MIN_HAIRPINS=2` 直接 422 | 【代码】main.py:161-170 | 1 hairpin 基因完全不能算 | 产品确认是否降级为“仅预检” |
| 18 | v1/v2 默认阈值不同，部署脚本又覆盖 | 【实测】config vs start 脚本 | 看 config 会误判现网 | 健康检查/日志显式打印参数 |
| 19 | `target_median_z` 只对 landmark 有值 | 【代码】signature_engine.py:263-268 | 非 landmark 靶点为 null | UI 标注 |
| 20 | 共享数据与 v2 副本语义不同 | 【实测】 | 同机两种数据语义 | 每个实例显式设置 `CMAP_DATA_DIR` |
| 21 | `fix_col_names.py` 依赖 h5py，不在运行时 requirements | 【代码】 | 部署机必须用 cmap 环境 | 文档已注明；可加脚本依赖说明 |
| 22 | v1 `export_store`/`figure3` 未做端到端验收 | 【推断】 | 不能保证现网可用 | 维护窗口冒烟 |
| 23 | v2 前端 `API_BASE` 硬编码 IP | 【实测】 | 换 IP/域名要改 HTML | 同源或构建时注入 |
| 24 | v1 `p_value` 只对 `obs<0` 计算 | 【代码】v1 drug_scorer.py:235-243 | score>=0 的药物 p 恒 1.0 | 文档说明；如需全方向 p 要改算法 |
| 25 | v1 Bootstrap 有放回且不排除目标列 | 【代码】v1 signature_engine.py:236-238 | v1 与 v2 p 值不可比 | 已在第 4/5 章标注；不要混用 |

---

## 6. 文档/交付说明中的不一致（已核实）

| 来源 | 原文/旧说法 | 实际 | 处理 |
|---|---|---|---|
| 部署完成报告 2026-10-18 第 4 节 | TP53 yellow “因为 gene_annotations.tsv 未配置” | 缺注释只加 reason；黄档由 `n_sig=43` 且 LOHO∈[0.3,0.5) 决定 | 在正文 5.4/6.2 与第 9 章标注；建议报告更正 |
| `deliveries/task-L7.md`、`docs/design/L7e-l3-provider.md` | 服务器只有 Level5，没有 L3/L4 | `/data2/wanggang/camp/level3`、`level4` 存在，v1 l4zsvc 在用 | 视为过时设计前提；正文 1.7/4.1 以实测为准 |
| `deliveries/task-L8.md` | 生成文件 md5 `9da43276fd375979f9e5e400ef42d00b` | 部署后 v2 实际 md5 `b7d0b45df6ad1db07b519103b2641984`（部署时重新生成） | 正文只引用部署实际 md5，旧 md5 不作为生产值 |
| `deliveries/task-L2.md` | 药物缓存名 `{GENE}_{h}_{method}_{mode}_drug_scores.json` | 当前代码是 `{GENE}_{h}_{method}_{fast}_{score}_drug_scores.json` | 正文以当前代码为准 |
| `deliveries/task-L4.md` | HTTP 层不暴露 `mode` | L3 已加 `mode`；当前 `ComputeRequest`/`/drugs` 都有 | 正文描述当前状态，历史说明注明 L3 引入 |
| `deliveries/task-L8.md` | “验收 1/3/4 在生产上成立”需行序修复 | 只修列序时 978 维向量近似不相关 | 正文第 3/8 章明确必须 `--fix-rows` |
| v1 口头/旧描述 | “FDA 按钮” | v1 前端没有 FDA 按钮；FDA 是内部药物范围过滤 | 正文 4.3 明确 |

---

## 7. 关键事实核对结果（v1 vs v2）

| 事实 | v1 | v2 | 证据 |
|---|---|---|---|
| 生产 provider | `l4zsvc` | `l5` | health + 代码 |
| 数据源 | `/data2/wanggang/camp/level3+level4` | `~/cmap_v2_data`（矩阵/GCTX 软链共享） | 代码 + 实测 |
| 是否受 L8 列/行序 bug 影响 | 生产不受；L5 路径会受影响 | 已修 CSV，已受保护 | 代码 + 实测 |
| 签名统计 | GSEA 式单侧 ES | 带符号 KS | 代码 |
| Bootstrap | 有放回、不排除目标列 | 无放回、排除目标列 | 代码 |
| 多重校正 | up/down 各自 BH | 全部基因一套 BH | 代码 |
| 阈值 | 0.001 / 100000（启动脚本） | 代码 0.05/1000；部署 0.001/100000 | 代码 + 实测 |
| 药物数 | 651（FDA） | 19,811（全部 trt_cp） | 实测 |
| 药物显著性 | p_value only | p/FDR/null_z | 代码 + 实测 |
| 适用性判档 | 无 | 有（yellow TP53 实测） | 实测 |
| 缓存版本化 | 无 | 有 | 代码 + 实测 |
| 导出/Figure3/Touchstone | 有 | 无 | 代码 |
| 前端 qc/FDR/红档 | 无 | 无（API 有） | 代码 |
| `all_scores` | 651 条 | 19,811 条 | 实测 |

---

## 8. 维护建议

1. 把 `docs/BACKEND_SITUATION.md` 当作“发布前必须更新”的清单；第 10.3 节列了触发条件。
2. 每次部署后至少更新：`health` 的 `available_genes/cached_signatures`、缓存文件名/形状、部署参数、TP53 回归值。
3. 任何缓存文件名/`signature_params()` 变化，必须同时更新第 2.6、3.4 和本文件第 5 节。
4. 任何统计口径变化，必须同时更新第 5 章并说明 v1/v2 是否可比。
5. 文档里的“实测值”是 2026-10-18 的点时快照，不能当作永久断言；重跑后回填。
6. 不要把 `gene_annotations.tsv`、药物映射大表、证书/密钥提交进 git。

---

## 9. 分支与提交

- 分支：`fix/docs-backend`
- 基线：`origin/main` @ `8d367b6`
- 本次只新增/修改：
  - `docs/BACKEND_SITUATION.md`
  - `deliveries/docs-backend.md`
- 推送：`git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 push -u origin fix/docs-backend`
- 具体 commit hash 见最终交付报告 / `git log -1 --oneline`。

> 并行任务提示：调查期间另有一个 L5 前端任务在运行；如果它先合并到 `fix/L5-frontend` 或 `main`，第 7.3 节“L5 未提交”和第 9 章第 3 项需要按实际提交更新。

## 10. 合并后更正（编排者补记）

本波合并顺序为 L5 先于文档（`4517e43` → `1850826`）。合并后已就地更正文中写于合并前的 3 处状态：

- §1.1 / 文档头：`origin/main` 由 `8d367b6` 更新为 `1850826`，注明基线关系；
- §7.3 / §9 第 3 项：删除“L5 未提交”，改为“L5 已合并；仍未完成的是导出/FDA 按钮移植”；
- §7.2 提交树补充 `4517e43` 与 `1850826` 两个合并提交。

章节结构（0–10 章）与其余核对结论不变。

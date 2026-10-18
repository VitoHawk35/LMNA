# DOC 系统交接文档 · 交付说明

## 1. 产物

| 产物 | 路径 | 说明 |
|---|---|---|
| 系统级交接文档 | `docs/SYSTEM_HANDOFF.md` | 2693 行（校验时点），0–12 章 + 附录 A；含 TOC、拓扑图、端口表、技术债台账、改进路线、决策清单 |
| 本交付说明 | `deliveries/docs-system-handoff.md` | 来源、实测更正、推断边界、待确认项、与既有文档分工 |
| README 入口 | `README.md` | 仓库原先没有 README；本次新建，顶部放交接文档链接，不覆盖任何既有内容 |

## 2. 信息来源

### 2.1 工作区与进度

| 来源 | 用途 |
|---|---|
| `D:\agent-workspace\README.md` | 工作区规则、服务器红线、SSH 方式、网络约定 |
| `D:\agent-workspace\PROGRESS.md` | D1–D10 决策、L0–L8/C0–C5/E0–E7 合并记录、测试计数、已知遗留 |
| `D:\agent-workspace\deliveries\deploy\部署完成报告-2026-10-18.md` | 新实例端口、目录、证书、L8 验收、TP53 预热、启动/回滚、已知差异 |
| `D:\agent-workspace\deliveries\deploy\新端口部署-cmap与LMNA.md` | 端口与访问地址复核 |
| `D:\agent-workspace\repos\LMNA`（baseline clone） | GitHub remote/default branch、HEAD、README 缺失确认 |
| `D:\agent-workspace\repos\cmap-l1000`（baseline clone） | GitHub remote/default branch、HEAD、路由、requirements、测试清单 |
| `D:\agent-workspace\repos\Easy_R_v2`（baseline clone） | GitHub remote/default branch、HEAD、测试清单、CI 缺失确认 |

### 2.2 LMNA 仓库文件（工作区 `task-DOC-HANDOFF`）

| 文件 | 读取内容 |
|---|---|
| `docs/BACKEND_SITUATION.md` | 1594 行全文；复用 v1/v2 差异、统计方法、L0–L8、缓存、已知问题；本文补充系统级视角 |
| `backend/config.py` | 全部环境变量、`ALGO_VERSION`、`signature_params()`、阈值、`DRUG_NULL_N`、`LMNA_ADMIN_TOKEN` |
| `backend/l5_provider.py` | memmap shape、L8 哨兵、列/行映射、landmark 过滤、`trt_sh`/`trt_cp` |
| `backend/drug_median_cache.py` | 版本化路径、锁、batch、中位数构建、原子替换 |
| `backend/drug_scorer.py` | mimic/score 符号、null、p/FDR、XSUM/WTCS 排序 |
| `backend/signature_engine.py` | 带符号 KS、bootstrap、BH、过滤、LOHO、qc |
| `backend/cache_manager.py` | 缓存键、路径、原子写、锁、清理 |
| `backend/task_queue.py` | 去重、进程池、超时、启动清理、inline |
| `backend/main.py` | 路由、CORS、静态 mount、删除缓存鉴权、`ComputeRequest`/`DrugQueryRequest` |
| `backend/suitability.py` | 规则 4.4 修订版、注释可选、LOHO、判档 |
| `backend/provider_factory.py` | l5/fixture/l3 |
| `backend/l3_provider.py` | 未实现 |
| `backend/fixture_provider.py` | 夹具四文件 |
| `frontend/index.html` | L5 的 `API_BASE=''`、适用性/FDR/fast 警告/`esc()`、Bootstrap CDN |
| `scripts/fix_col_names.py` | GCTX COL/ROW 修复、`--check/--in-place/--fix-rows/--verify`、备份、原子写 |
| `scripts/verify_drug_median.py` | 旧缓存名硬编码、行序诊断、`--from` 真值、阈值 |
| `requirements.txt`、`.gitignore` | 依赖与忽略规则 |
| `deliveries/task-L0.md` … `task-L8.md` | 各任务验收、测试数、部署动作 |

### 2.3 cmap-l1000 仓库文件

| 文件 | 读取内容 |
|---|---|
| `app/config.py` | 数据路径、drug median 路径、`CMAP_NULL_N/SEED/BATCH/MIN_GENES`、`CSV_TOP_N_MAX`、Touchstone |
| `app/main.py` | CORS、路由注册、同源静态路由、启动清理 |
| `app/api/tau_search.py` | `/submit_tau`、`/tau_job`、废弃 `/search_tau`、结果组装 |
| `app/scoring/null_calibrator.py` | C3 算法、符号、p/BH/null_z、状态 |
| `app/models/schemas.py` | `TauSearchResult` 的 `p_value/fdr/null_z`、`null_calibration` |
| `app/core/matrix_store.py` | memmap 单例、shape、chunk |
| `app/core/metadata_index.py` | sig/gene 索引 |
| `app/core/post_processor.py` | NCS/聚合/Tau |
| `index.html` | Vue2、`apiBaseUrl:''`、本地资源、API 调用 |
| `start.sh` / `start_all.sh` / `stop*.sh` / `status.sh` | `-w 1 --threads 8`、端口 8001、PID/日志、screen 8081 |
| `deploy/cmap.service`、`deploy/nginx.conf` | systemd 旧配置、旧 IP 反代 |
| `scripts/build_drug_median.py` | `--from-lmna`、输出三文件、raw float32 说明 |
| `tests/test_*.py` | 8 个文件、39 个 `def test_` |
| `requirements*.txt` | 依赖最低版本、gunicorn |

### 2.4 Easy_R_v2 仓库文件

| 文件 | 读取内容 |
|---|---|
| `backend/app/settings.py` | `DATA_DIR`、`DEMO_DATA_PATH` |
| `backend/app/main.py` | CORS、路由注册、`/api/health` |
| `backend/app/services/auth_service.py` | PBKDF2 120k、HMAC token、7 天、密钥优先级与文件 |
| `backend/app/services/report_service.py` | 文件名正则、用户 reports 目录、docx/pdf、E7a 文案 |
| `backend/app/routers/report.py` | generate/download、鉴权、realpath 限制 |
| `backend/app/services/data_service.py` | 用户目录、数据集 registry、上传/预览、缺失值策略 |
| `backend/app/routers/*.py` | auth/datasets/diagnostics/eval/history/ml/report 路由清单 |
| `backend/requirements.txt` | 锁定版本、Python 3.11 依赖 |
| `frontend/package.json` | React18/Vite5/vitest/scripts |
| `frontend/.env.production` | `VITE_API_BASE_URL=/api` |
| `frontend/src` | `api.ts`、`sanitizeSvg.test.ts`、`WizardContext.test.ts` |
| `backend/tests/*.py` | 6 个 pytest 文件、39 个 `def test_` |
| `deliveries/` E0–E7 | 各任务验收、测试数、上线动作 |

### 2.5 服务器只读核对命令

全部通过 `ssh -i ~/.ssh/lmna_deploy keji@10.39.15.238` 执行，未做任何写操作。

| 类别 | 命令 |
|---|---|
| 时间 | `date` |
| 端口 | `ss -ltnp` |
| 进程 | `ps -eo pid,ppid,lstart,cmd`、`/proc/<pid>/cmdline`、`/proc/<pid>/cwd` |
| 目录 | `ls -la`、`find`、`stat`、`readlink -f`、`du -sh` |
| 脚本 | `cat ~/start_new_instances.sh`、`stop_new_instances.sh`、各 `start_v2.sh`/`stop_v2.sh`、`~/portal/restart_all.sh`、`~/portal/start.sh` |
| systemd | `systemctl list-unit-files`、`systemctl cat portal-stack.service`、`is-enabled`、`is-active` |
| nginx | `ls -la /etc/nginx` |
| 证书 | `openssl x509 -noout -subject -dates`、`ls -l *.key` |
| 数据 | `ls -la ~/cmap_v2_data`、`stat`、`md5sum`（4 个 CSV）、`du -sh` |
| 缓存 | `ls -lh ~/lmna_v2_cache`、`cat *.shape.txt` |
| 日志 | `tail` 各实例日志 |
| 健康 | `curl -k` 对 8007/8004/8008/8888/8001 |
| 运行环境 | `tr '\0' '\n' < /proc/<pid>/environ`，仅 grep 非敏感项 |
| 部署代码 | `find ~/cmap_v2/app`、`grep null/fdr/p_value`、`grep routes` |
| 前端 | `grep API_BASE/suitability/fdr/fast_mode`、`stat` |

## 3. 对既有“已实测事实”的更正/补充

| 旧说法 | 本次实测 | 处理 |
|---|---|---|
| “LMNA_v2 API 8004 有重复 uvicorn 进程，`start_v2.sh` 幂等性可疑” | 不是重复服务：父 2797792 + 两个 `ProcessPoolExecutor` 子进程 2799377/2799378；子进程继承监听 socket fd；启动时间晚 2 分钟，正好对应首次预热 | 在 1.7 明确澄清；不作为缺陷，但提醒 stop 需杀进程组 |
| “cmap 旧实例与仓库一致” | 旧 8001 实测 `-w 4`，仓库 `start.sh` 是 `-w 1 --threads 8`；旧 config 无 `CSV_TOP_N_MAX`，代码更旧 | 在 1.3/3.5/10 记录 |
| “cmap C3 已合并（可能被理解为已上线）” | GitHub `40dfe9c` 已合并；线上 `~/cmap_v2` 是 `0a02aa3`，无 `null_calibrator.py`、无 `build_drug_median.py`、schema 无 p/fdr/null_z | 在 2.5/3.9/10 标为部署滞后 |
| “LMNA L5 已合并（可能被理解为已上线）” | GitHub `25851f9` 已合并；线上前端 13,299 bytes，无适用性/FDR/fast/esc，`API_BASE` 硬编码 8004 | 在 2.5/4.8/10 标为部署滞后 |
| “cmap_data 23GB” | `fast_matrix.npy` 是 23,356,480,864 bytes；`~/cmap/cmap_data` 目录 64G；`~/cmap_v2_data` 仅 34M（大文件软链 + 两个实体 CSV） | 在 1.2/2.3 精确区分 |
| “新数据目录是两应用共用” | 共用的是大文件（软链）；CSV 是新实体；LMNA 另有独立缓存 | 在 2.2/2.3 说明 |
| “D7 默认 500，可改 150” | `app/config.py` 实际默认 `150` | 在 10/I15、12/N8 标记矛盾 |
| “LMNA 仓库有 README” | `origin/main` 无 `README.md` | 本次新建 README，见产物表 |

## 4. 只能由 v1 代码/推断得出、未在本次实测的结论

以下内容没有在服务器上逐行执行/验证，属于“据代码推断”或“来自既有文档”，在正文中已标注：

1. LMNA v1 的 `l4zsvc` 具体重建逻辑、`/data2/wanggang/camp/level3|4` 的文件组织、ZSVC 参数；
2. v1 的 `/figure3`、`/api/export_data`、FDA 过滤的前端交互细节；
3. v1 统计口径与 v2 的逐项数值差异（仅知道 D1 后旧结论作废）；
4. LMNA 缓存的命中/失效在真实并发下的行为；
5. `ProcessPoolExecutor` 子进程在 `stop_v2.sh` 执行后的最终状态（未做停止演练）；
6. cmap C3 在 473,647 全库上的真实耗时（只测了 978×19,811 的 null 部分）；
7. cmap WTCS 全库扫描耗时、内存峰值；
8. memmap 冷读/热读性能；
9. Easy_R 各建模算法的真实耗时与并发表现；
10. 三仓库的代码覆盖率（无 coverage 配置）；
11. 旧 cmap 使用旧 CSV 时具体错列的比例/影响（只确认 CSV 顺序不一致，未做业务对比）；
12. `restart_all.sh` 在异常端口占用下的实际行为；
13. systemd 重启后新实例的手工拉起流程（未重启服务器验证）。

## 5. 需要人工确认的事项

### 5.1 既有决策

| 编号 | 事项 | 当前状态 |
|---|---|---|
| D4 | `gene_annotations.tsv` 是否上线、数据源与许可 | 待定 |
| D5 | Touchstone 用 GSE92742 还是 LINCS2020 | 待定 |
| D7 | CSV topN 默认 150 还是 500（代码与 PROGRESS 矛盾） | 待确认 |
| D9 | CDN 离线化范围（LMNA Bootstrap 仍走 CDN） | 待定 |
| D10 | P3 统一系统是否启动 | 待定 |
| L4 | `M=2000 + fdr<0.01` 验收口径 | 待确认 |

### 5.2 本次新增

| 编号 | 事项 | 建议 |
|---|---|---|
| N1 | 是否立即部署 C3 到 8007 | 建议是；需先构建 `drug_median_lm.npy` |
| N2 | 是否部署 L5 前端并同源 | 建议同源 |
| N3 | 药物 null/FDR 生产口径（M、BH 家族、UI 说明） | 短期 UI 明示，中期受限 BH |
| N4 | D4 注释表来源/许可 | 建议上线，先确认许可 |
| N5 | Easy_R 是否上 HTTPS | 建议随统一入口一起做 |
| N6 | 新实例是否进 systemd/门户 | 建议单独 `new-stack.service` |
| N7 | l4zsvc/FDA/Figure3/export 是否移植 | 先移植导出 |
| N8 | D7 默认值统一 | 建议默认 150 |
| N9 | 旧 cmap 升级/下线 | 先标注历史，再升级/下线 |
| N10 | 统一入口/认证是否启动 | 建议分阶段 |
| N11 | 数据 manifest/启动自检 | 建议做 |
| N12 | CI 与发布流程 | 建议做 |
| N13 | 备份/容灾 | 建议先备份 CSV/manifest/缓存元数据 |
| N14 | 监控/告警 | 建议先做端口/健康/磁盘 |

### 5.3 需要业务方确认的事实

1. 8007 是否就是 cmap 的“新版权威入口”，还是仅试用；
2. 8004/8084 是否就是 LMNA 的“新版权威入口”；
3. Easy_R_v2_next 是否准备替换旧 Easy_R_v2，何时冻结旧实例写入；
4. 旧 cmap 8001/8081 是否还有用户依赖，能否加“历史/不保证正确”提示；
5. v1 的 FDA/Figure3/导出功能是否有真实用户，优先级如何；
6. 患者数据/报告的最短保留期与删除要求；
7. 是否允许把内网端口暴露给更大范围网络。

## 6. 与 `docs/BACKEND_SITUATION.md` 的分工

| 内容 | BACKEND_SITUATION | SYSTEM_HANDOFF |
|---|---|---|
| LMNA 后端字段级 API | 详细 | 只列路由与关键字段 |
| 统计公式推导 | 详细 | 只列口径/符号/限制 |
| v1 路由/按钮/缓存 | 详细 | 只列“未移植”清单 |
| L0–L8 修复细节 | 详细 | 索引 + 系统影响 |
| 三系统拓扑/端口/多租户 | 无 | 本文 |
| cmap/Easy_R 现状 | 无 | 本文 |
| 部署版本 vs GitHub HEAD | 部分 | 本文实测更正 |
| 安全矩阵/CI/覆盖率 | 无 | 本文 |
| 技术债台账/改进路线/决策 | 部分（已知问题 1–20） | 本文系统化 |
| 只读核对命令 | 有 LMNA 版 | 本文扩展为三系统 |

建议维护方式：

- `BACKEND_SITUATION.md` 继续作为 LMNA 后端“深文档”；
- 本文作为“总交接/运维/决策”入口；
- 两者冲突时，以本文标注“实测（日期/命令）”的内容为准，并在本文 0.3 节记录变更。

## 7. 未完成项与原因

| 项 | 原因 |
|---|---|
| 未做停止/重启演练 | 任务红线要求只读，不得重启服务 |
| 未做服务器重启验证 | 同上，且会影响多租户 |
| 未对 23GB 矩阵做全量 MD5 | 耗时/IO 成本高，且只读窗口不适合 |
| 未做全库 WTCS 性能实测 | 会占用大量 CPU/IO，影响生产 |
| 未做 coverage 报告 | 仓库未配置 coverage 工具 |
| 未部署 C3/L5 | 本任务仅文档；部署需单独决策与窗口 |
| 未修改任何业务代码 | 任务要求只做文档 |
| 未提交大数据/密钥 | 数据红线 |

## 8. 数据红线声明

本次交付未包含、未提交：

- 证书私钥（`*.key`）；
- `LMNA_ADMIN_TOKEN`、`EASYR_AUTH_SECRET`、`auth_secret.txt` 内容；
- 用户 `users.json`、上传 CSV、报告 docx/pdf；
- `fast_matrix.npy`、GCTX、缓存文件；
- 任何患者数据。

文档中只出现路径、文件名、大小、权限、CN/有效期等非敏感元数据。

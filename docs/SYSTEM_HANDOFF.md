# LMNA / CMAP-L1000 / Easy_R_v2 系统级交接文档（SYSTEM_HANDOFF）

> 文档版本：v1.0
> 编写日期：2026-10-18
> 适用对象：第一次接触本项目、需要独立接手部署与后续演进的人或 AI
> 代码基线：LMNA `origin/main@25851f9`；cmap-l1000 `origin/master@40dfe9c`；Easy_R_v2 `origin/main@b3c6ae9`
> 运行基线：共享服务器 `10.39.15.238`（登录用户 `keji`）上的旧/新两套实例

---

## 目录

- [0. 元信息](#0-元信息)
  - [0.1 文档目的](#01-文档目的)
  - [0.2 目标读者与使用方式](#02-目标读者与使用方式)
  - [0.3 维护责任](#03-维护责任)
  - [0.4 数据与安全红线](#04-数据与安全红线)
  - [0.5 证据等级与标记](#05-证据等级与标记)
  - [0.6 与 `docs/BACKEND_SITUATION.md` 的分工](#06-与-docsbackend_situationmd-的分工)
- [1. 系统全景与部署拓扑](#1-系统全景与部署拓扑)
  - [1.1 三个应用分别是什么](#11-三个应用分别是什么)
  - [1.2 全景 ASCII 图](#12-全景-ascii-图)
  - [1.3 端口总表（含多租户邻居）](#13-端口总表含多租户邻居)
  - [1.4 证书、HTTPS 与 nginx 现状](#14-证书https-与-nginx-现状)
  - [1.5 门户导航与开机自启动](#15-门户导航与开机自启动)
  - [1.6 启动、停止、回滚](#16-启动停止回滚)
  - [1.7 PID、日志与进程形态](#17-pid日志与进程形态)
  - [1.8 多租户边界与风险](#18-多租户边界与风险)
- [2. 三仓库关系与数据耦合](#2-三仓库关系与数据耦合)
  - [2.1 仓库总表](#21-仓库总表)
  - [2.2 代码与数据耦合关系](#22-代码与数据耦合关系)
  - [2.3 数据目录布局](#23-数据目录布局)
  - [2.4 算法符号约定（最容易混用的部分）](#24-算法符号约定最容易混用的部分)
  - [2.5 部署版本与 GitHub HEAD 的差异](#25-部署版本与-github-head-的差异)
- [3. cmap-l1000 现状](#3-cmap-l1000-现状)
  - [3.1 架构与技术栈](#31-架构与技术栈)
  - [3.2 API 清单](#32-api-清单)
  - [3.3 C0–C5 修复历史](#33-c0c5-修复历史)
  - [3.4 C3：随机签名 null、p 值与 BH-FDR](#34-c3随机签名-nullp-值与-bh-fdr)
  - [3.5 `-w 1 --threads 8` 的原因与边界](#35--w-1---threads-8-的原因与边界)
  - [3.6 Vue2 前端与静态资源](#36-vue2-前端与静态资源)
  - [3.7 数据层](#37-数据层)
  - [3.8 性能实测](#38-性能实测)
  - [3.9 部署现状：GitHub 已合并 C3，但 8007 未运行 C3](#39-部署现状github-已合并-c3但-8007-未运行-c3)
- [4. LMNA 现状](#4-lmna-现状)
  - [4.1 两代 LMNA](#41-两代-lmna)
  - [4.2 后端模块逐文件说明](#42-后端模块逐文件说明)
  - [4.3 数据层](#43-数据层)
  - [4.4 缓存结构与版本化](#44-缓存结构与版本化)
  - [4.5 L0–L8 修复历史](#45-l0l8-修复历史)
  - [4.6 v1 与 v2 差异清单（含“未移植”）](#46-v1-与-v2-差异清单含未移植)
  - [4.7 纯 HTML 前端（L5）](#47-纯-html-前端l5)
  - [4.8 部署现状：后端 8d367b6、前端仍是 L5 之前版本](#48-部署现状后端-8d367b6前端仍是-l5-之前版本)
- [5. Easy_R_v2 现状](#5-easy_r_v2-现状)
  - [5.1 架构与技术栈](#51-架构与技术栈)
  - [5.2 E0–E7 修复历史](#52-e0e7-修复历史)
  - [5.3 认证与密钥](#53-认证与密钥)
  - [5.4 报告生成与下载安全](#54-报告生成与下载安全)
  - [5.5 CORS、上传限制与前端安全](#55-cors上传限制与前端安全)
  - [5.6 数据副本与“不自动同步”语义](#56-数据副本与不自动同步语义)
  - [5.7 前端构建](#57-前端构建)
  - [5.8 端口与部署形态](#58-端口与部署形态)
- [6. 数据血缘与可复现性](#6-数据血缘与可复现性)
  - [6.1 数据来源](#61-数据来源)
  - [6.2 `fast_matrix.npy` 与 GCTX 的真值关系](#62-fast_matrixnpy-与-gctx-的真值关系)
  - [6.3 列序/行序修复脚本](#63-列序行序修复脚本)
  - [6.4 缓存重建手册](#64-缓存重建手册)
  - [6.5 夹具与环境变量](#65-夹具与环境变量)
  - [6.6 校验和、快照与当前缺口](#66-校验和快照与当前缺口)
- [7. 安全现状与缺口](#7-安全现状与缺口)
  - [7.1 认证矩阵](#71-认证矩阵)
  - [7.2 密钥与文件权限](#72-密钥与文件权限)
  - [7.3 CORS 白名单](#73-cors-白名单)
  - [7.4 自签证书](#74-自签证书)
  - [7.5 上传限制](#75-上传限制)
  - [7.6 报告下载安全](#76-报告下载安全)
  - [7.7 LMNA 删除缓存鉴权](#77-lmna-删除缓存鉴权)
  - [7.8 多租户边界](#78-多租户边界)
  - [7.9 安全缺口清单](#79-安全缺口清单)
- [8. 测试与 CI 现状](#8-测试与-ci-现状)
  - [8.1 三仓库测试脚手架](#81-三仓库测试脚手架)
  - [8.2 测试命令](#82-测试命令)
  - [8.3 CI 现状](#83-ci-现状)
  - [8.4 覆盖率估计与依据](#84-覆盖率估计与依据)
- [9. 性能现状与瓶颈](#9-性能现状与瓶颈)
  - [9.1 LMNA 预热与缓存](#91-lmna-预热与缓存)
  - [9.2 cmap 的 `-w 1` 阻塞模型](#92-cmap-的--w-1-阻塞模型)
  - [9.3 memmap 冷读与 chunk](#93-memmap-冷读与-chunk)
  - [9.4 各层缓存策略](#94-各层缓存策略)
  - [9.5 已测性能数据](#95-已测性能数据)
  - [9.6 瓶颈排序](#96-瓶颈排序)
- [10. 已知问题与技术债台账](#10-已知问题与技术债台账)
- [11. 距离“成熟可靠”的差距与改进建议](#11-距离成熟可靠的差距与改进建议)
  - [11.1 统一入口与 HTTPS](#111-统一入口与-https)
  - [11.2 进程与自启动](#112-进程与自启动)
  - [11.3 监控、日志与告警](#113-监控日志与告警)
  - [11.4 CI 与测试](#114-ci-与测试)
  - [11.5 数据校验与快照](#115-数据校验与快照)
  - [11.6 统一认证与权限](#116-统一认证与权限)
  - [11.7 统计口径与产品化](#117-统计口径与产品化)
  - [11.8 功能补齐与统一系统](#118-功能补齐与统一系统)
- [12. 人工决策清单](#12-人工决策清单)
  - [12.1 既有 D1–D10](#121-既有-d1d10)
  - [12.2 本次新增决策 N1–N12](#122-本次新增决策-n1n12)
  - [12.3 建议决策顺序](#123-建议决策顺序)
- [附录 A：只读核对命令速查](#附录-a只读核对命令速查)

---

## 0. 元信息

### 0.1 文档目的

本文件回答四个问题：

1. 这台服务器上到底跑着哪些系统，端口、目录、进程、数据分别是什么；
2. 三个 GitHub 仓库与线上实例之间是什么关系，哪些修复已经合并、哪些真正部署；
3. 每个系统的统计口径、缓存、数据血缘和安全边界是什么；
4. 如果要把它从“能用的科研原型”推进到“成熟可靠的生产系统”，下一步应当做什么、需要谁决策。

本文不是 API 使用手册，也不是算法论文。它是**系统交接与运维决策文档**。字段级的 API 说明、统计公式推导、v1 代码细节，见 `docs/BACKEND_SITUATION.md`（1594 行）；本文在其基础上补齐系统级视角，并对该文档未覆盖的部署差异做了实测更正。

### 0.2 目标读者与使用方式

目标读者是“聪明但完全不了解本项目的人或 AI”。因此：

- 首次出现的术语都会解释；
- 所有关键路径使用服务器绝对路径或仓库相对路径；
- 所有命令都可以直接复制执行（除明确标注“危险/需人工确认”的写操作）；
- 事实与推断严格分开，不把猜测写成事实；
- 对“文档说有、机器上没有”的差异，以实测为准并显式标注。

推荐阅读顺序：

1. 第 0、1、2 章：建立全景；
2. 第 10 章：先看风险台账；
3. 第 11、12 章：看改进路线与待决策项；
4. 需要深挖某个系统时，再读第 3、4、5 章；
5. 需要重建数据或排查正确性时，读第 6、9 章。

### 0.3 维护责任

| 项目 | 约定 |
|---|---|
| 维护触发条件 | 新增/下线实例、端口变化、部署新版本、数据目录迁移、证书轮换、统计口径变化、重大故障后 |
| 建议维护人 | 系统接手人（当前为 `keji` 账号的实际负责人）；每次变更由变更执行人更新对应章节 |
| 更新方式 | 只改事实与日期，不删除历史；已失效结论标注“已作废”并保留原因 |
| 评审要求 | 涉及统计口径、安全边界、生产部署的修改，需要用户/项目负责人确认 |
| 关联文档 | `docs/BACKEND_SITUATION.md`（LMNA 细节）、`deliveries/task-L*.md`、`deliveries/task-C*.md`、`deliveries/task-E*.md`、`deliveries/deploy/*.md` |
| 文档位置 | LMNA 仓库 `docs/SYSTEM_HANDOFF.md`；交付说明在 `deliveries/docs-system-handoff.md` |

### 0.4 数据与安全红线

以下红线适用于所有后续维护者：

1. **不得把大数据提交到 Git**：`*.npy`、`*.gctx`、`cache/`、`temp/`、用户上传数据、报告文件均不入库。
2. **不得把密钥、证书私钥、患者数据写入文档或提交**：包括 `lmna.key`、`cmap.key`、`auth_secret.txt`、`LMNA_ADMIN_TOKEN`、用户 `users.json`、上传 CSV、报告 docx/pdf。
3. **不得在服务器上做未授权的写操作**：本交接核查全程只读；生产变更必须在部署窗口由人执行。
4. **不得触碰多租户邻居**：`8000/8002/8080/8082/8888/9000–9003` 等属于其他项目或其他用户，任何重启、杀进程、改配置都可能影响他人。
5. **不得引用本机历史副本中的证书/患者数据**：仓库与文档只描述服务器上的路径与文件名，不复述内容。
6. **不得把“GitHub 已合并”当成“线上已生效”**：本服务器已经出现两次部署滞后（C3、L5 前端），必须按第 2.5 节核对。

### 0.5 证据等级与标记

本文使用三种标记：

| 标记 | 含义 | 示例 |
|---|---|---|
| 「实测（2026-10-18，命令）」 | 在服务器或仓库上直接执行只读命令得到的结果 | `ss -ltnp`、`ps -eo ...`、`openssl x509`、`curl` |
| 「据代码推断」 | 通过阅读仓库代码/配置得到、未在生产规模实测的结论 | 缓存键包含 `DRUG_NULL_N` |
| 「待确认」 | 需要用户/负责人决定，或需要进一步实测 | D4 注释表是否上线 |

补充约定：

- 端口、进程、PID、文件大小、权限、证书日期均为 2026-10-18 12:30–12:40 CST 的实测快照；
- 进程 PID 会随重启变化，文档记录 PID 仅用于说明“当时形态”，不应作为长期标识；
- 性能数字注明来源（交付文档实测或本次本机健康检查），不把健康检查耗时当作业务耗时；
- 统计结论注明样本量与口径，旧口径结论明确标注作废。

### 0.6 与 `docs/BACKEND_SITUATION.md` 的分工

| 维度 | `BACKEND_SITUATION.md` | 本文 `SYSTEM_HANDOFF.md` |
|---|---|---|
| 范围 | LMNA 单系统后端 | 三系统 + 服务器 + 三仓库 |
| 深度 | 字段级 API、公式、v1 路由、缓存文件格式 | 部署拓扑、跨仓库数据耦合、安全、性能、技术债、改进路线 |
| 读者 | 要改 LMNA 后端的人 | 要接手整套系统、做运维与产品决策的人 |
| 已覆盖 | LMNA 模块、统计方法、L0–L8、重建手册、已知问题 1–20 | 不重复推导；引用其结论，补充系统级事实 |
| 本文新增 | cmap/Easy_R 现状、统一拓扑、多租户、CI、安全矩阵、决策清单、部署滞后实测 | — |
| 冲突处理 | 以本文标注“实测”的更新事实为准，并在交付说明中列出差异 | — |

---

## 1. 系统全景与部署拓扑

### 1.1 三个应用分别是什么

| 应用 | 一句话定位 | 主要用户动作 | 核心输出 |
|---|---|---|---|
| **cmap-l1000** | LINCS L1000 药物扰动数据库检索与疾病逆转筛选 | 输入疾病上/下调基因或药物名，搜索 473,647 个扰动签名 | 候选药物排名、Tau/WTCS 分数、p/FDR、CSV/图表 |
| **LMNA** | 基因敲低（shRNA）签名构建与逆转药物预测 | 输入基因名，计算其敲低签名并筛药 | 上调/下调基因、KS 显著性、适用性档位、药物排名 |
| **Easy_R_v2** | 临床预测模型/统计建模工作台 | 上传临床 CSV，做缺失诊断、特征筛选、建模、验证、报告 | 模型指标、图表、Word/PDF 报告、历史记录 |

三者的共同点：都是 FastAPI 后端 + 浏览器前端；都部署在同一台内网服务器；都使用自签证书或明文 HTTP；都没有统一登录（Easy_R 除外，它有自己的账号体系）。

三者的关键区别：

- cmap 和 LMNA 共享同一份 L1000 矩阵数据，算法都围绕“签名逆转”；
- Easy_R 与另外两者**没有数据耦合**，只是恰好部署在同一台机器；
- cmap 是“疾病签名 → 药物”，LMNA 是“基因敲低签名 → 药物”，二者方向相近但数据源与打分实现不同，**结论不能互相替代**。

### 1.2 全景 ASCII 图

```text
                              用户浏览器（内网）
                                     |
        +----------------------------+-----------------------------+
        |                            |                             |
        | 旧入口（门户 8888 仍指向）  | 新入口（未加入门户）          | 独立入口
        v                            v                             v
+-------------------+        +-------------------+          +---------------------+
| cmap 旧实例       |        | cmap_v2           |          | Easy_R 旧实例       |
| API  :8001 HTTPS  |        | API  :8007 HTTPS  |          | API  :8005 HTTP     |
| 前端 :8081 HTTP   |        | 前端同源 /        |          | 前端 :8090 HTTP     |
| 代码 ~/cmap       |        | 代码 ~/cmap_v2    |          | 代码 ~/Easy_R       |
| 数据 ~/cmap/      |        | 数据 ~/cmap_v2_   |          | 数据 ~/Easy_R/      |
|      cmap_data    |        |      data(软链)   |          |      backend/data   |
+---------+---------+        +---------+---------+          +---------------------+
          |                            |
          |                            +-------------------+
          |                            |                   |
          |                            v                   v
          |                  +-------------------+  +---------------------+
          |                  | LMNA v1           |  | LMNA v2             |
          |                  | API  :8003 HTTPS  |  | API  :8004 HTTPS    |
          |                  | 前端 :8083 HTTPS  |  | 前端 :8084 HTTPS    |
          |                  | 代码 ~/lmna_app/  |  | 代码 ~/lmna_v2      |
          |                  |      LMNA         |  | 缓存 ~/lmna_v2_cache|
          |                  | 数据 /data2/...   |  | 数据 ~/cmap_v2_data |
          |                  +-------------------+  +---------------------+
          |                            |                   |
          |                            +---------+---------+
          |                                      |
          v                                      v
+--------------------------+          +--------------------------+
| ~/cmap/cmap_data (64G)   |          | ~/cmap_v2_data (34M 目录) |
| fast_matrix.npy 23.36GB  |<--软链--| fast_matrix.npy -> 旧目录 |
| GCTX / sig_info / ...    |<--软链--| GCTX / gene_info -> 旧目录|
| col_sig_ids.csv (旧序!)  |          | col_sig_ids.csv (已修)    |
| row_gene_ids.csv (旧序!) |          | row_gene_ids.csv (已修)   |
+--------------------------+          +--------------------------+

+---------------------+        +---------------------+        +---------------------+
| Easy_R_v2 旧实例    |        | Easy_R_v2_next      |        | 其他租户/项目       |
| API  :8006 HTTP     |        | API  :8008 HTTP     |        | 8000/8002/8080/8082 |
| 前端 :8091 HTTP     |        | 前端 :8092 HTTP     |        | 9000-9003 / 8888    |
| 数据 ~/Easy_R_v2/   |        | 数据 ~/Easy_R_v2_   |        | 不属于本交接范围    |
|      backend/data   |        |      next_data(副本)|        | 禁止操作            |
+---------------------+        +---------------------+        +---------------------+
```

说明：

- 图中“旧入口”指 `~/portal/index.html` 当前仍链接的地址；新实例没有加入门户。
- `~/cmap_v2_data` 只有 34MB 的目录元数据，大文件全部是指向 `~/cmap/cmap_data` 的软链接；真正占空间的是 `~/cmap/cmap_data`（实测 64G）。
- 旧 cmap 与旧 LMNA v1 使用各自的历史数据/代码路径；新 LMNA v2 使用修正后的 CSV 与独立缓存。

### 1.3 端口总表（含多租户邻居）

「实测（2026-10-18，`ss -ltnp` + `ps -eo pid,ppid,lstart,cmd` + `/proc/<pid>/cwd`）」

| 端口 | 服务 | 进程形态（实测） | 协议 | 代码目录 | 数据/备注 |
|---:|---|---|---|---|---|
| 22 | SSH | sshd | TCP | — | 管理入口 |
| 6379 | Redis | redis-server | TCP | — | 仅本机，非本交接业务 |
| 8000 | Bio_info API | uvicorn（bioinfo 环境，Python 3.10） | HTTP | 其他项目 | **多租户邻居，禁动** |
| 8001 | cmap 旧 API | gunicorn `-w 4` + 4 workers（5 个进程） | HTTPS | `~/cmap` | 数据 `~/cmap/cmap_data`；旧 CSV/旧代码 |
| 8002 | Bio_R API | uvicorn（Bio_R 环境） | HTTP | 其他项目 | **多租户邻居，禁动** |
| 8003 | LMNA v1 API | `python3 main.py` + 2 个进程池子进程 | HTTPS | `~/lmna_app/LMNA/backend` | 数据源 `l4zsvc`，不走 fast_matrix |
| 8004 | LMNA v2 API | `python3 -m uvicorn main:app` + 2 个进程池子进程 | HTTPS | `~/lmna_v2/backend` | `DATA_PROVIDER=l5`，数据 `~/cmap_v2_data` |
| 8005 | Easy_R 旧 API | uvicorn（easyr 环境，Python 3.11） | HTTP | `~/Easy_R/backend` | 旧版，门户仍在用 |
| 8006 | Easy_R_v2 旧 API | uvicorn（easyr 环境） | HTTP | `~/Easy_R_v2/backend` | 数据 `~/Easy_R_v2/backend/data` |
| 8007 | cmap_v2 API + 前端 | gunicorn `-w 1 --threads 8` + 1 worker | HTTPS | `~/cmap_v2` | 同源托管 Vue2 页面；**运行代码不含 C3** |
| 8008 | Easy_R_v2_next API | uvicorn（easyr 环境） | HTTP | `~/Easy_R_v2_next/backend` | 数据 `~/Easy_R_v2_next_data` |
| 8080 | Bio_info 前端 | `python3 -m http.server` | HTTP | 其他项目 | **多租户邻居，禁动** |
| 8081 | cmap 旧前端 | `python3 -m http.server`（screen `cmap-web`） | HTTP | `~/cmap` | 指向 8001 |
| 8082 | Bio_R 前端 | `python3 -m http.server` | HTTP | 其他项目 | **多租户邻居，禁动** |
| 8083 | LMNA v1 前端 | 自定义 Python HTTPS 静态服务 | HTTPS | `~/lmna_app/LMNA/frontend` | 指向 8003 |
| 8084 | LMNA v2 前端 | `serve_frontend_v2.py`（http.server + TLS） | HTTPS | `~/lmna_v2/frontend` | 页面内 `API_BASE=https://10.39.15.238:8004` |
| 8090 | Easy_R 旧前端 | `npx serve dist -p 8090 --cors` | HTTP | `~/Easy_R/frontend` | 指向 8005 |
| 8091 | Easy_R_v2 旧前端 | `npx serve dist -p 8091 --cors` | HTTP | `~/Easy_R_v2/frontend` | 指向 8006 |
| 8092 | Easy_R_v2_next 前端 | `npx serve dist -p 8092 --cors` | HTTP | `~/Easy_R_v2_next/frontend` | 构建产物直连 8008 |
| 8888 | 门户导航页 | `python3 -m http.server` | HTTP | `~/portal` | 只链接旧实例 |
| 9000 | GPS4Drugs | uvicorn（gps4drugs-web 环境） | HTTP | 其他项目 | **多租户邻居，禁动** |
| 9001 | Bulk RNA-seq | uvicorn（bulk_rnaseq_workflow 环境） | HTTP | 其他项目 | **多租户邻居，禁动** |
| 9002 | DrugReflector | uvicorn | HTTP | 其他项目 | **多租户邻居，禁动** |
| 9003 | GEO Fetch | node（vite preview） | HTTP | 其他项目 | **多租户邻居，禁动** |
| 50022 | 备用 SSH | sshd | TCP | — | 系统层 |
| 8787 | 未识别监听 | — | TCP | — | 与本项目无关，禁动 |

补充：

- `127.0.0.1:631` 是 CUPS，`127.0.0.53/54:53` 是 systemd-resolved，`127.0.0.1:6379` 是 Redis，均不对外。
- 旧 cmap 的 `-w 4` 与仓库当前 `start.sh` 的 `-w 1 --threads 8` 不一致，原因是旧进程于 2026-09-10 启动，早于 C2 的部署参数调整；不要据此认为仓库配置错误。
- 8003/8004 的“多个 PID”不是重复服务，见 1.7 的澄清。

### 1.4 证书、HTTPS 与 nginx 现状

「实测（2026-10-18，`openssl x509 -noout -subject -dates`；`ls /etc/nginx`）」

| 项目 | 实测结果 |
|---|---|
| nginx | **未安装**：`/etc/nginx` 不存在，`/etc/nginx/conf.d` 不存在 |
| 反向代理 | **没有**统一反代；每个实例直接监听端口 |
| 证书 CN | `CN = 10.39.15.238`（IP 直连，非域名） |
| 有效期 | `notBefore = Jun 19 19:39:00 2026 GMT`；`notAfter = Jun 16 19:39:00 2036 GMT` |
| 证书文件 | `~/cmap/certs/cmap.crt`、`~/cmap_v2/certs/cmap.crt`、`~/lmna_app/LMNA/backend/lmna.crt`、`~/lmna_app/LMNA/frontend/lmna.crt`、`~/lmna_v2/backend/lmna.crt`、`~/lmna_v2/frontend/lmna.crt` |
| 私钥权限 | `-rw------- keji keji`（0600），1704 bytes |
| 证书类型 | 自签证书；浏览器首次访问会提示不受信任 |
| HTTP 实例 | Easy_R 全部三个实例（8005/8006/8008 与 8090/8091/8092）均为明文 HTTP |

这意味着：

- 目前没有“统一域名 + 统一 443 + 统一登录”的入口；
- 每个应用各自处理 HTTPS，自签证书的信任问题无法集中解决；
- D2 设计的“nginx 同源反代 `/api`”**没有落地**，实际是跨端口直连；
- Easy_R 的登录令牌与用户数据在明文 HTTP 上传输，内网可用但不符合生产安全基线。

### 1.5 门户导航与开机自启动

「实测（2026-10-18，`cat ~/portal/index.html`、`cat ~/portal/restart_all.sh`、`systemctl is-enabled/is-active portal-stack.service`）」

门户现状：

- `~/portal/index.html` 是静态导航页，监听 `8888`；
- 门户链接的地址为：`https://10.39.15.238:8001`（cmap 旧）、`http://10.39.15.238:8080`（Bio_info）、`http://10.39.15.238:8082`（Bio_R）、`http://10.39.15.238:8090`（Easy_R 旧）、`https://10.39.15.238:8003`（LMNA 旧）、`http://10.39.15.238:9000–9003`；
- **门户没有链接 8007/8084/8008/8092 等任何新实例**；
- 门户没有链接 Easy_R_v2 旧实例（8006/8091）。

自启动现状：

- 唯一相关 systemd unit：`/etc/systemd/system/portal-stack.service`；
- 状态：`enabled` + `active`；
- 类型：`Type=oneshot`、`RemainAfterExit=yes`、`User=keji`；
- 执行：`/home/keji/portal/restart_all.sh`；
- `restart_all.sh` 覆盖：portal 8888、cmap 8001/8081、LMNA 8003/8083、Bio_info 8000/8080、Bio_R 8002/8082、Easy_R 8005/8090、GPS 9000、BulkRNA 9001、DrugReflector 9002、GEO Fetch 9003；
- **不覆盖任何新实例**；服务器重启后新实例不会自动拉起，必须手工执行 `bash ~/start_new_instances.sh`。

`restart_all.sh` 的幂等策略：

```bash
# 对每个端口发一次 HTTP 请求（含 404 也视为在跑），通则跳过
up() {
  local k=""; [ "${2:-http}" = "https" ] && k="-k"
  curl $k -s -o /dev/null --max-time 5 "${2:-http}://127.0.0.1:$1/"
}
```

该策略只判断“端口有响应”，不判断响应是否来自正确进程、版本是否正确、健康检查是否通过；因此可能出现“端口被别的进程占用但脚本误判为已启动”的情况。

### 1.6 启动、停止、回滚

以下命令均为服务器上可复制的命令。生产执行前先确认当前版本与数据目录。

一键启动/停止新实例：

```bash
ssh -i ~/.ssh/lmna_deploy keji@10.39.15.238
bash ~/start_new_instances.sh
bash ~/stop_new_instances.sh
```

`~/start_new_instances.sh` 内容（实测）：

```bash
#!/usr/bin/env bash
set -euo pipefail
bash /home/keji/cmap_v2/start_v2.sh
bash /home/keji/lmna_v2/start_v2.sh
bash /home/keji/lmna_v2/start_frontend_v2.sh
bash /home/keji/Easy_R_v2_next/start_v2.sh
echo "all new instances started"
```

`~/stop_new_instances.sh` 内容（实测）：

```bash
#!/usr/bin/env bash
set -uo pipefail
bash /home/keji/Easy_R_v2_next/stop_v2.sh || true
bash /home/keji/lmna_v2/stop_frontend_v2.sh || true
bash /home/keji/lmna_v2/stop_v2.sh || true
bash /home/keji/cmap_v2/stop_v2.sh || true
echo "all new instances stopped"
```

单实例启动：

```bash
# cmap_v2（8007，HTTPS，同源前端）
bash ~/cmap_v2/start_v2.sh

# LMNA_v2 API（8004，HTTPS）
bash ~/lmna_v2/start_v2.sh

# LMNA_v2 前端（8084，HTTPS）
bash ~/lmna_v2/start_frontend_v2.sh

# Easy_R_v2_next（8008 API + 8092 前端）
bash ~/Easy_R_v2_next/start_v2.sh
```

单实例停止：

```bash
bash ~/cmap_v2/stop_v2.sh
bash ~/lmna_v2/stop_v2.sh
bash ~/lmna_v2/stop_frontend_v2.sh
bash ~/Easy_R_v2_next/stop_v2.sh
```

旧实例启停（由 `restart_all.sh` 管理，非必要不要单独操作）：

```bash
bash ~/cmap/start_all.sh
bash ~/cmap/stop_all.sh
bash ~/lmna_app/LMNA/start.sh
bash ~/lmna_app/LMNA/stop.sh
bash ~/portal/restart_all.sh
```

回滚新实例：

```bash
# 只停新实例，老服务不受影响
bash ~/stop_new_instances.sh

# 彻底删除新实例（危险！会删除新缓存与数据副本，需人工确认）
rm -rf ~/cmap_v2 ~/lmna_v2 ~/Easy_R_v2_next \
       ~/cmap_v2_data ~/lmna_v2_cache ~/cmap_v2_temp \
       ~/Easy_R_v2_next_data ~/Easy_R_v2_next_secrets ~/lmna_v2_verify
```

回滚注意：

- 删除 `~/cmap_v2_data` 不会删除 `~/cmap/cmap_data` 的原始大文件，但会丢失修正后的 CSV；重建需按第 6.3 节重新生成。
- 删除 `~/lmna_v2_cache` 会丢失预热结果，下次首次计算需重新预热（TP53 约 6 分钟量级）。
- 旧实例的停止脚本会按 PID 文件和 `pkill` 清理；不要在新实例运行期间执行 `pkill -f uvicorn` 之类的宽匹配命令，否则会误杀其他租户服务。

### 1.7 PID、日志与进程形态

「实测（2026-10-18，`cat` PID 文件、`ps`、`/proc/<pid>/cwd`、`/proc/<pid>/cmdline`）」

| 实例 | PID 文件 | 日志 | 实测 PID（快照） |
|---|---|---|---|
| cmap_v2 API | `~/cmap_v2/.cmap_v2.pid` | `~/cmap_v2/cmap_v2.log` | 2797754（master）/ 2797762（worker） |
| LMNA_v2 API | `~/lmna_v2/.lmna_v2.pid` | `~/lmna_v2/server_v2.log` | 2797792（父）/ 2799377、2799378（池子进程） |
| LMNA_v2 前端 | `~/lmna_v2/.lmna_frontend_v2.pid` | `~/lmna_v2/frontend_v2.log` | 2797795 |
| Easy_R_v2_next API | `~/Easy_R_v2_next/.backend.pid` | `~/Easy_R_v2_next/backend_v2.log` | 2797988 |
| Easy_R_v2_next 前端 | `~/Easy_R_v2_next/.frontend.pid` | `~/Easy_R_v2_next/frontend_v2.log` | 2797991 |
| LMNA v1 API | `~/lmna_app/LMNA/cache/lmna_server.pid`（据启动脚本） | `~/lmna_app/LMNA/backend/server.log` | 2916474（父）/ 2917856、2917857（池子进程） |
| cmap 旧 API | `~/cmap/.cmap-api.pid` | `~/cmap/cmap-api.log` | 1876466（master）/ 4 workers |
| Easy_R 旧 API | 旧脚本管理 | 旧目录日志 | 3333354 |
| Easy_R_v2 旧 API | 旧脚本管理 | 旧目录日志 | 1770558 |

**关键澄清：8004/8003 不是重复 uvicorn。**

之前的交接材料把 8004 上的多个 PID 描述为“重复 uvicorn 进程”，本次实测证明这是误判：

- 8004 父进程 `2797792` 启动于 `01:45:36`；
- 两个子进程 `2799377`、`2799378` 启动于 `01:47:26`，父进程均为 `2797792`；
- 三个进程的 `/proc/<pid>/cmdline` 完全相同，`cwd` 均为 `/home/keji/lmna_v2/backend`；
- 子进程出现的时间正好是首次预热任务提交的时间；
- 代码中 `ProcessPoolExecutor(max_workers=2)` 会 fork 两个 worker；fork 后子进程继承父进程的监听 socket fd，因此 `ss -ltnp` 会显示三个 PID 都监听 8004。

结论：这是**进程池 worker 继承监听 socket**，不是两个独立服务，也不是 `start_v2.sh` 重复启动。8003 的 v1 也是同样形态（其启动脚本甚至专门写了“先杀 worker 子进程，否则端口占用”的注释）。

运维含义：

- 停止服务时必须先杀子进程再杀父进程，或直接杀进程组；`~/lmna_app/LMNA/start_server.sh stop` 已经这样处理；
- 新实例的 `stop_v2.sh` 需要确认是否也清理子进程；从当前脚本看只处理 PID 文件中的父进程，若父进程退出后子进程仍存活，可能残留监听端口（**待实测/待确认**）；
- 看到多个 PID 不要惊慌，也不要手工 `kill` 其中一个，否则可能破坏进程池。

### 1.8 多租户边界与风险

服务器是多人共享的生产/科研混合环境。实测发现其他用户/项目：

- `/home/wanggang/.vscode-server`、`/home/yumh/.vscode-server` 等开发进程；
- `8000/8002/8080/8082` 的 Bio_info/Bio_R；
- `9000–9003` 的 GPS4Drugs、Bulk RNA-seq、DrugReflector、GEO Fetch；
- `8888` 门户、`6379` Redis、`631` CUPS。

风险：

1. **没有容器/命名空间隔离**：所有进程都以各自用户运行，但共享同一内核、同一网络命名空间、同一磁盘；
2. **端口冲突**：任何新服务启动前必须 `ss -ltnp` 确认端口未被占用；
3. **误杀风险**：`pkill -f uvicorn`、`pkill -f python` 会波及其他租户；
4. **资源竞争**：cmap 全库扫描、Easy_R 建模、LMNA bootstrap 都是 CPU/内存密集型，可能互相拖慢；
5. **权限边界弱**：同组用户可能读取彼此文件；密钥文件虽为 0600，但数据目录多为组可读；
6. **重启影响面大**：`portal-stack.service` 的 `restart_all.sh` 会拉起多个租户服务，修改它需协调所有使用者。

操作纪律：

- 只操作自己负责的 PID/端口；
- 变更前先记录 `ss -ltnp` 快照；
- 不在业务高峰做全库扫描或缓存重建；
- 不修改 `/etc/systemd/system` 下不属于本项目的 unit；
- 不删除、不重建共享数据目录下的原始文件。

---

## 2. 三仓库关系与数据耦合

### 2.1 仓库总表

「实测（2026-10-18，`git remote -v`、`git branch -r`、`git log -1`）」

| 仓库 | GitHub | 默认分支 | 当前 HEAD | 技术栈 | Python/运行时 | 线上部署版本 |
|---|---|---|---|---|---|---|
| LMNA | `https://github.com/VitoHawk35/LMNA.git` | `main` | `25851f9`（docs: 更正 L5 合并后的过时状态） | FastAPI + 纯 HTML/JS | Python 3.10（`cmap` conda 环境） | 后端 `8d367b6`；前端 L5 之前 |
| cmap-l1000 | `https://github.com/VitoHawk35/cmap-l1000.git` | `master` | `40dfe9c`（Merge C3） | FastAPI + Vue2 单页 | Python 3.10（`cmap` 环境） | `0a02aa3`（C1/C2/C4，**不含 C3**） |
| Easy_R_v2 | `https://github.com/VitoHawk35/Easy_R_v2.git` | `main` | `b3c6ae9`（Merge E6） | FastAPI + React18/Vite5 | Python 3.11（`easyr` 环境） | `b3c6ae9`（E5/E6） |

仓库关系：

- 三个仓库相互独立，没有 submodule、没有共享包；
- cmap 与 LMNA 只通过**共享数据目录**耦合，不通过代码依赖；
- Easy_R 与另外两者完全独立；
- 三个仓库都没有 `.github/workflows`，即**没有 CI**（见第 8 章）。

### 2.2 代码与数据耦合关系

```text
+----------------------+          +----------------------+
| cmap-l1000           |          | LMNA                 |
| FastAPI + Vue2       |          | FastAPI + HTML       |
+----------+-----------+          +----------+-----------+
           |                                 |
           | 读取                             | 读取
           v                                 v
+----------------------+          +----------------------+
| ~/cmap/cmap_data     |<--软链---| ~/cmap_v2_data       |
| - fast_matrix.npy    |          | - fast_matrix.npy -> |
| - GCTX               |          | - col_sig_ids.csv    |
| - sig_info/gene_info |          | - row_gene_ids.csv   |
| - 旧列序 CSV         |          | - 其他元数据软链     |
+----------------------+          +----------+-----------+
                                             |
                                             | LMNA 私有
                                             v
                                  +----------------------+
                                  | ~/lmna_v2_cache      |
                                  | - 秩矩阵 .v2.dat     |
                                  | - 药物中位数 .v2.npy |
                                  | - signatures/        |
                                  | - drug_scores/       |
                                  | - tasks/             |
                                  +----------------------+

+----------------------+          +----------------------+
| Easy_R / Easy_R_v2   |          | Easy_R_v2_next       |
| 各自 backend/data    |          | ~/Easy_R_v2_next_data|
| 用户/上传/报告/密钥  |          | （88MB 独立副本）    |
+----------------------+          +----------------------+
```

关键结论：

1. cmap 与 LMNA 的“共享”只在数据文件层，不在代码层；任一方的代码升级不会自动影响另一方。
2. `~/cmap_v2_data` 不是完整副本：大文件是软链接，只有两个 CSV 是实体文件；因此“复制 `cmap_v2_data`”并不等于“备份了 23GB 矩阵”。
3. LMNA v2 的药物中位数矩阵是从共享 GCTX 重新构建的私有缓存，位于 `~/lmna_v2_cache`，不在 `cmap_v2_data`。
4. Easy_R 的三个实例各有一份数据目录；`Easy_R_v2_next_data` 是 `Easy_R_v2/backend/data` 的副本，后续不会自动同步。

### 2.3 数据目录布局

| 路径 | 类型/大小（实测） | 内容 | 谁在用 |
|---|---|---|---|
| `~/cmap/cmap_data` | 目录，64G | 原始 L1000 数据：`fast_matrix.npy`（23,356,480,864 bytes）、GCTX、sig_info、gene_info、pert_info、cell_info、旧列序 CSV | 旧 cmap 8001；新实例通过软链共享大文件 |
| `~/cmap_v2_data` | 目录，34M | 大文件软链到 `~/cmap/cmap_data`；实体 `col_sig_ids.csv`（17,433,427 bytes，0600）、`row_gene_ids.csv`（67,518 bytes，0600）；旧 CSV 备份 `.bak-20261018-014410` | cmap_v2 8007、LMNA v2 8004 |
| `~/cmap_v2_temp` | 目录 | cmap_v2 任务/导出临时文件 | cmap_v2 |
| `~/lmna_v2_cache` | 目录，369M | `_shrna_rank_matrix.v2.154993.dat`（303,166,308 bytes）、shape `978,154993`；`_drug_median_matrix.v2.npy`（77,500,760 bytes）；`_drug_names.v2.csv`（268,566 bytes）；`signatures/`、`drug_scores/`、`tasks/` | LMNA v2 |
| `~/Easy_R/backend/data` | 目录 | 旧 Easy_R 用户、上传、报告、`auth_secret.txt` | Easy_R 8005 |
| `~/Easy_R_v2/backend/data` | 目录 | Easy_R_v2 旧实例数据 | Easy_R_v2 8006 |
| `~/Easy_R_v2_next_data` | 目录，88M | 独立副本：`demo.csv`、上传 CSV、历史 docx、用户目录 | Easy_R_v2_next 8008 |
| `~/Easy_R_v2_next_secrets/auth_secret.txt` | 文件，64 bytes，0600 | 认证密钥（不记录内容） | Easy_R_v2_next |
| `/data2/wanggang/camp/level3`、`level4` | 目录（v1 数据源） | LMNA v1 `l4zsvc` 使用的 ZSVC 重建数据 | LMNA v1 8003 |
| `~/lmna_app/LMNA/backend/trt_sh_isgold.csv` | 文件，18,816,432 bytes | v1 的 shRNA 金标准表 | LMNA v1 |

路径注意：

- 旧 cmap 的 `~/cmap/cmap_data/col_sig_ids.csv` 仍是**旧排序**，旧 cmap 代码没有 L8 哨兵检查，因此旧实例可能按错误列序取数；这是已知高风险技术债（见第 10 章）。
- `~/cmap_v2_data` 的 CSV 权限为 0600，只有 `keji` 可读；服务以 `keji` 运行，正常；若未来改为其他用户运行，需要调整权限。
- 不要把 `~/cmap_v2_data` 当作独立备份；备份策略必须单独覆盖 `~/cmap/cmap_data` 的实体大文件。

### 2.4 算法符号约定（最容易混用的部分）

| 系统/算法 | 分数定义 | 哪个方向表示“逆转” | 显著性/排序 | 备注 |
|---|---|---|---|---|
| cmap WTCS | 加权连接分数，范围约 -1~1 | **负值** = 逆转 | 按 WTCS 从小到大取 top；Tau 最负为 top | CMAP 官方口径 |
| cmap XSUM（C3） | `xsum = Σ z(up) − Σ z(down)` | **负值** = 逆转 | `p_reversal` 取 null 的下尾；BH 后 `fdr_reversal` 越小越显著 | `p_value`/`fdr` 字段分别映射 reversal |
| cmap Tau | 对 WTCS 做 NCS 归一化与药物聚合后的分数 | **越负** = 越逆转 | `top_results` 为 tau 最负 | C5 设计中 |
| LMNA 签名 KS | 带符号 KS：`KS>0` 富集在上调方向，`KS<0` 富集在下调方向 | 由 up/down 基因集合表达 | 过滤 `fdr<阈值` 且 `abs(ks)>阈值` | L1 修正后口径 |
| LMNA 药物 XSUM | `mimic = Σ z(up) − Σ z(down)`；`score = −mimic` | **score 高** = 逆转（与 mimic 相反） | lof 模式按 `fdr_reversal` 升序 + `score` 降序 | 与 cmap 的“负=逆转”方向相反，务必注意 |
| LMNA 药物 WTCS | 按列排名加权，`(G+1)-2*rank` | 由 score 方向决定 | 无 p/FDR/null_z | 与 XSUM 不同，不能直接比较 |
| LMNA 药物 null | 随机签名重算 mimic/xsum | `p_reversal` 为下尾，`null_z` 越负越逆转 | BH 跨药物校正 | `DRUG_NULL_N=10000` |
| Easy_R | 无“逆转”概念 | — | AUC/PR-AUC/Brier/DCA 等 | 临床预测模型 |

记忆口诀：

- **cmap：负的是好药（逆转）**；
- **LMNA XSUM：分数越高越是好药**（因为 `score = −mimic`）；
- **两边都叫 `fdr_reversal`，但底层分数方向相反**，跨系统比较排名前必须确认符号。

### 2.5 部署版本与 GitHub HEAD 的差异

这是本交接最重要的系统级发现之一。

| 系统 | GitHub HEAD | 线上实际版本 | 差异 | 证据 |
|---|---|---|---|---|
| LMNA 后端 | `25851f9` | `8d367b6`（L2 合并点） | 缺 L5 前端；后端已含 L2/L3/L4/L6/L8 | 部署报告明确写“前端合并版 8d367b6”；`~/lmna_v2/backend` 有 `suitability.py`、`drug_median_cache.py` |
| LMNA 前端 | `25851f9`（L5 已合并） | L5 之前版本（13,299 bytes） | 无适用性卡片、无 FDR 列、无 `fast_mode` 警告、无 `esc()` 转义；`API_BASE` 硬编码 | 实测 `grep` 只找到 `API_BASE`，没有 `suitability/fdr_reversal/fast_mode`；文件大小 13,299 |
| cmap | `40dfe9c`（C3 已合并） | `0a02aa3`（C1/C2/C4） | **完全没有 C3**：无 `app/scoring/null_calibrator.py`、无 `scripts/build_drug_median.py`、schemas 无 p/fdr/null_z、config 无 null 配置 | 实测 find/grep；部署报告表也写 `0a02aa3（C1/C2/C4）` |
| Easy_R_v2 | `b3c6ae9` | `b3c6ae9` | 一致 | 部署报告 + 实测 dist 含 8008 地址 |

结论：

- “合并”只代表代码进入 GitHub 主分支，**不代表服务器已部署**；
- 交接时必须区分“仓库状态”和“运行状态”；
- 任何“已验证 C3/L5”的说法，必须绑定到具体实例与具体命令；
- 本文件后续提到 C3/L5 时，会明确写“GitHub 代码”还是“线上 8007/8084”。

---

## 3. cmap-l1000 现状

### 3.1 架构与技术栈

cmap-l1000 是 LINCS L1000 数据检索与疾病逆转筛选服务。

| 层 | 实现 | 说明 |
|---|---|---|
| Web 框架 | FastAPI | 路由集中在 `app/api/`，统一前缀 `/api/v1` |
| ASGI 服务器 | gunicorn + `uvicorn.workers.UvicornWorker` | 生产 `-w 1 --threads 8`；旧实例 `-w 4` |
| 数据访问 | NumPy `memmap` | `app/core/matrix_store.py` 单例，零拷贝读取 23.36GB 矩阵 |
| 元数据 | Pandas | `sig_info`、`gene_info`、`pert_info`、`cell_info` |
| 打分 | NumPy + 自定义 scorer | `app/scoring/`：cosine、WTCS、null calibration |
| 前端 | Vue 2 单文件 HTML | `index.html` 1529 行；本地化 Bootstrap/Vue/ECharts |
| 耗时任务 | 后台线程 + JSON job 文件 | Tau 全库扫描异步化（C2） |
| 进程模型 | 单 worker + 8 线程 | 共享 memmap，避免多进程各自映射 23GB |

Python 环境：

- 服务器 conda 环境名：`cmap`；
- 解释器：`/home/keji/miniconda3/envs/cmap/bin/python3.10`；
- 依赖：`requirements.txt` 为最低版本约束（`fastapi>=0.68`、`uvicorn>=0.15`、`numpy>=1.19`、`pandas>=1.3`、`h5py>=3.0`、`pydantic>=1.8`、`python-multipart>=0.0.5`、`scipy>=1.7`、`openpyxl>=3.0`）；`requirements-prod.txt` 额外含 `gunicorn>=20.1.0`。

### 3.2 API 清单

「据代码（`app/api/*.py`）」

| 方法 | 路径 | 用途 | 关键输入/输出 |
|---|---|---|---|
| POST | `/api/v1/parse_csv` | 解析用户上传的 CSV，提取基因列 | 文件 + 列名；返回解析结果 |
| POST | `/api/v1/convert_to_ids` | 基因 symbol → Entrez ID | 基因列表；返回映射 |
| POST | `/api/v1/extract` | 按药物/细胞系/剂量提取扰动签名 | `pert_iname`、`cell_id`、`dose`；返回 12328 维向量 |
| POST | `/api/v1/search` | 余弦/XSUM 类疾病逆转搜索 | up/down 基因；返回 top/bottom 药物 |
| POST | `/api/v1/search_wtcs` | WTCS 搜索（同步） | up/down 基因；返回分数与排名 |
| POST | `/api/v1/search_wtcs_stream` | WTCS 流式搜索 | 同上，SSE/流式返回 |
| POST | `/api/v1/submit_tau` | 提交 Tau 全库扫描任务（C2 异步） | up/down 基因、top_k；返回 `job_id` |
| GET | `/api/v1/tau_job/{job_id}` | 查询 Tau 任务状态/结果 | `job_id`；返回进度与结果 |
| POST | `/api/v1/search_tau` | 同步 Tau 搜索（已废弃） | 同上；保留兼容 |
| POST | `/api/v1/export` | 导出搜索结果 zip | 结果数据；返回文件 |
| POST | `/api/v1/export_wtcs` | 导出 WTCS 结果 zip | 结果数据；返回文件 |
| POST | `/api/v1/export_data` | 生成通用导出 token（C2） | 数据；返回临时 token |
| GET | `/api/v1/export_data/{token}` | 凭 token 下载导出文件 | token；返回文件 |
| GET | `/health` | 健康检查 | 返回 `{"status":"healthy"}` |
| GET | `/` | 同源托管前端页面 | 返回 `index.html` |
| GET | `/echarts.min.js` | 本地 ECharts | 静态文件 |
| GET | `/bootstrap.min.css` | 本地 Bootstrap | 静态文件 |
| GET | `/vue.min.js` | 本地 Vue | 静态文件 |

注意：

- C3 的 `p_value/fdr/null_z` 不是独立路由，而是 `TauSearchResult` 的新字段，随 `/submit_tau`/`/tau_job`（以及废弃的 `/search_tau`）返回；
- 线上 8007 的 `TauSearchResult` 目前没有这三个字段（C3 未部署）；
- 旧 8001 的代码更旧，连 C1 的 `CSV_TOP_N_MAX` 都没有，CSV topN 行为与仓库 master 不一致。

### 3.3 C0–C5 修复历史

「据 PROGRESS 合并记录 + 交付文档」

| 任务 | 分支 | 合并提交 | 内容 | 测试 |
|---|---|---|---|---|
| C0 | `fix/C0-test-scaffold` | `8093b78` | 测试脚手架；配置环境变量化（`CMAP_DATA_DIR` 等） | 6 tests |
| C1 | `fix/C1-topk-150` | `06a3ea2` | CSV 导出 topN 上限；`CSV_TOP_N_MAX` 可配置；稳定排序 | 14 tests |
| C2 | `fix/C2-async-deploy` | `4c27b66` | Tau 异步任务；事件循环阻塞修复；部署参数 `-w 1 --threads 8`；启动清理未完成任务 | 13 tests |
| C3 | `fix/C3-null-fdr` | `631f433` / merge `40dfe9c` | 随机签名 null → p 值/BH-FDR/null_z；药物中位数构建脚本；缺失矩阵降级 | 39 passed 1 skipped |
| C4 | `fix/C4-reskin` | `0a02aa3` | 前端换肤；Bootstrap/Vue/ECharts 本地化（约 327KB）；静态路由 | 21 tests |
| C5 | `docs/C5-touchstone-tau` | `b86de21` | Touchstone/Tau 方案 A 设计文档 | 文档 |

当前 master HEAD：`40dfe9c`（Merge C3）。

### 3.4 C3：随机签名 null、p 值与 BH-FDR

C3 解决的问题：Tau/WTCS 分数本身没有显著性，用户无法判断“排名第一”是真实信号还是随机波动。

算法口径（`app/scoring/null_calibrator.py`）：

1. 查询基因集合为 `up`/`down`，长度分别为 `U`/`D`；
2. 从 978 个 landmark 基因中**无放回**随机抽取同样长度的基因，构造随机签名；
3. 对每个药物计算 `xsum = Σ z(up) − Σ z(down)`；
4. 重复 `M=CMAP_NULL_N` 次（默认 10000），得到该药物的 null 分布；
5. `p_reversal = (count(null <= observed) + 1) / (M + 1)`（下尾，越负越逆转）；
6. 对所有药物做 Benjamini–Hochberg 校正，得到 `fdr_reversal`；
7. `null_z = (observed − mean(null)) / sd(null)`，越负表示越偏离随机；
8. 结果按 `pert_iname` 左连接到 Tau 结果；`p_value ← p_reversal`，`fdr ← fdr_reversal`。

`null_calibration` 状态：

| 状态 | 含义 |
|---|---|
| `ok` | 正常完成 |
| `insufficient_landmark_genes` | 查询基因中可用于抽样的 landmark 基因不足 |
| `unavailable` | 药物中位数矩阵缺失/不可读，降级为无 p/FDR |

药物中位数矩阵：

- 构建脚本：`scripts/build_drug_median.py`；
- 输出：`drug_median_lm.npy`（978 × n_drug）、`drug_median_names.csv`、`drug_median_lm_gene_ids.csv`；
- 支持 `--from-lmna` 复用 LMNA 的 `_drug_median_matrix.v2.npy` / `_drug_names.v2.csv`；
- 注意 `fast_matrix.npy` 是**无 `.npy` 头的 raw float32**，脚本按 shape 手动 memmap。

关键限制：

- `M=10000` 时单次 p 值分辨率下限为 `1/10001 ≈ 1e-4`；
- 生产规模约 19811 个药物，BH 家族大小约 19811，孤立命中的 FDR 下限约为 `19811 × 1e-4 ≈ 1.98`，**大于 1，意味着按 FDR<0.05 不可能显著**；
- 因此 C3 的 p/FDR 在默认 M 下更适合“相对排序/诊断”，不适合作为“显著药物”的硬判据；
- 要得到有意义的 FDR，需要把 M 提高到 `~2e6` 量级，或限制 BH 家族（如只对 top-K 药物校正），或改用其他校准策略。这是 12.2 的 N3 决策。

实测性能（C3 交付文档，真实矩阵）：

- 样本：978 landmark × 19,811 药物；
- `M=10000`；
- 单次耗时 1.416 秒；
- 峰值内存 206.8MB。

### 3.5 `-w 1 --threads 8` 的原因与边界

D6 决定：生产使用 `gunicorn -w 1 --threads 8 -k uvicorn.workers.UvicornWorker`。

原因：

1. **内存**：每个进程都会 mmap 23.36GB 矩阵。`-w 4` 会让 4 个 worker 各自持有映射与页缓存引用，内存压力与冷读重复风险更高；
2. **GIL**：主要计算在 NumPy/SciPy 中，释放 GIL，多线程可以并行；
3. **状态一致性**：单进程内 job store、metadata index、memmap 单例只有一份，避免多进程重复加载；
4. **阻塞隔离**：C2 把长任务放到后台线程/线程池，避免阻塞事件循环；8 个线程足以覆盖并发请求。

边界：

- 单 worker 意味着**没有进程级故障隔离**：worker 崩溃，服务整体不可用；
- 8 线程共享同一进程内存，单个超大请求可能拖慢所有请求；
- Python 层的纯 Python 计算仍受 GIL 限制；
- 如果未来引入 `ProcessPoolExecutor` 做 CPU 密集任务，子进程会继承监听 socket，`ss` 会显示多个 PID（LMNA 已经出现），需要按进程组管理。

与旧实例的差异：

- 旧 cmap 8001 实测仍是 `-w 4 -k uvicorn.workers.UvicornWorker`；
- 旧实例启动于 2026-09-10，早于 C2 的 `-w 1 --threads 8` 调整；
- 旧实例同时缺少 C1/C3，不能把新实例的验证结果套到旧实例。

### 3.6 Vue2 前端与静态资源

`index.html`（1529 行）是 Vue2 单页应用：

- `apiBaseUrl: ''`，默认同源，请求 `/api/v1/...`；
- 本地资源：`bootstrap.min.css`（232,919 bytes）、`vue.min.js`（94,156 bytes）、`echarts.min.js`（1,030,900 bytes）；
- 主要调用：`parse_csv`、`convert_to_ids`、`search`、`search_wtcs_stream`、`submit_tau`、`tau_job`、`extract`、`export_data`、`download`；
- C4 已把 CDN 资源本地化，静态路由为 `/bootstrap.min.css`、`/vue.min.js`、`/echarts.min.js`；
- 仓库根目录还有一份 10.4MB 的参考文献 PDF 和若干图片，不属于运行时依赖，但会增大仓库体积（建议后续移到 `docs/` 或 LFS，**待确认**）。

同源部署：

- 8007 的 FastAPI 在 `/` 返回 `index.html`，因此前端与 API 同源；
- CORS 默认不启用（`CMAP_CORS_ORIGINS` 为空）；
- 如果未来把前端放到 8081 或独立域名，需要显式配置 CORS。

### 3.7 数据层

| 文件 | 作用 | 关键约束 |
|---|---|---|
| `fast_matrix.npy` | 12328 × 473647 的 float32 矩阵，原始无 `.npy` 头 | 列序 = GCTX COL 顺序；行序 = GCTX ROW 顺序 |
| `col_sig_ids.csv` | 473647 个 `sig_id`，列索引映射 | 必须是 GCTX COL 顺序；旧文件是字典序，已修 |
| `row_gene_ids.csv` | 12328 个 `gene_id`，行索引映射 | 必须是 GCTX ROW 顺序；旧文件错位 4/12328，已修 |
| `GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx` | 原始 GCTX 真值 | 列 = 扰动签名，行 = 基因 |
| `GSE92742_Broad_LINCS_sig_info.txt.gz` | 签名元数据 | `sig_id`、`pert_iname`、`pert_type`、`cell_id`、`pert_idose` |
| `GSE92742_Broad_LINCS_gene_info.txt.gz` | 基因元数据 | `pr_is_lm=1` 为 978 landmark |
| `GSE92742_Broad_LINCS_pert_info.txt.gz` | 扰动元数据 | 药物/基因/对照 |
| `GSE92742_Broad_LINCS_cell_info.txt.gz` | 细胞系元数据 | 细胞系名称/谱系 |

`app/core/matrix_store.py`：

- 单例；
- `np.memmap(..., dtype='float32', mode='r', shape=(12328, 473647))`；
- `get_column(k)` / `get_columns(positions)` 返回副本；
- 批量迭代 chunk 10000；
- 不做写操作。

`app/core/metadata_index.py`：建立 `sig_id → 列索引`、`gene_id → 行索引`、药物/细胞系过滤。

`app/core/post_processor.py`：NCS 归一化、药物聚合、Tau 排序。

### 3.8 性能实测

| 场景 | 数据 | 结果 | 来源 |
|---|---|---|---|
| C3 null 校准 | 978 landmark × 19,811 药物，M=10000 | 1.416s，峰值 206.8MB | C3 交付文档 |
| C3 null 校准（旧数据） | 978 × 19,811，M=10000 | 1.42s / 207MB | PROGRESS |
| 服务健康检查 | `GET /health`，本机 | 12.6ms（HTTP 200） | 本次实测（curl） |
| 旧实例健康检查 | `GET /health`，本机 | 14.0ms（HTTP 200） | 本次实测（curl） |
| 全库 WTCS 扫描 | 473647 签名 | 未在本次交接中实测；C2 交付称耗时以分钟计 | 待实测 |
| memmap 冷读 | 23.36GB | 未实测 | 待实测 |

注意：健康检查耗时只说明进程存活与事件循环可用，不代表业务请求耗时。

### 3.9 部署现状：GitHub 已合并 C3，但 8007 未运行 C3

「实测（2026-10-18，`find ~/cmap_v2/app`、`grep`、`ls`）」

线上 `~/cmap_v2` 的文件清单：

- `app/api/`：`csv_parser.py`、`export.py`、`export_data.py`、`export_wtcs.py`、`extract.py`、`search.py`、`tau_search.py`、`wtcs_search.py`；
- `app/core/`：`export_store.py`、`job_store.py`、`matrix_store.py`、`metadata_index.py`、`post_processor.py`；
- `app/scoring/`：`base_scorer.py`、`cosine_scorer.py`、`wtcs_scorer.py`；
- **没有** `app/scoring/null_calibrator.py`；
- **没有** `scripts/build_drug_median.py`；
- `app/models/schemas.py` 中没有 `p_value`/`fdr`/`null_z`；
- `app/config.py` 中没有 `NULL_CALIBRATION_N`/`CMAP_NULL_*`；
- `app/api/tau_search.py` 的 `TauSearchResult(...)` 只组装旧字段；
- 部署目录中的 `deliveries/` 只有 C0/C1/C2/C4/C5，没有 C3；
- 部署报告明确写 `cmap_v2` 为 `0a02aa3（C1/C2/C4）`。

因此：

- 线上 8007 的 Tau 结果**没有 p_value/fdr/null_z**；
- 线上 8007 的“C3 已部署”说法不成立；
- 如果用户看到 8007 没有 FDR 列，不是前端问题，而是后端版本未更新；
- 部署 C3 是 N1 决策，且需要同时部署 `build_drug_median.py` 与药物中位数矩阵。

---

## 4. LMNA 现状

### 4.1 两代 LMNA

| 代际 | 路径 | 端口 | 数据源 | 状态 |
|---|---|---|---|---|
| v1（现网旧版） | `~/lmna_app/LMNA` | 8003 API / 8083 前端 | `DATA_PROVIDER=l4zsvc`，ZSVC 重建数据（`/data2/wanggang/camp/level3|4`） | 仍在运行；含 l4zsvc/FDA/Figure3/export |
| v2（新修复版） | `~/lmna_v2` | 8004 API / 8084 前端 | `DATA_PROVIDER=l5`，`~/cmap_v2_data` 的 fast_matrix | 后端 `8d367b6`；前端 L5 之前 |

v1 的关键事实（来自 `BACKEND_SITUATION.md` 与本次只读核对）：

- `start_server.sh` 固定论文参数：`DATA_PROVIDER=l4zsvc`、`BOOTSTRAP_N=100000`、`FDR_THRESHOLD=0.001`、`KS_THRESHOLD=0.2`、`FAST_MODE_TOP_N=0`、`DRUG_PERM_N=10000`、`API_PORT=8003`；
- 数据源不是 fast_matrix，而是 `l4zsvc` 的 ZSVC 重建数据；
- 因此 v1 与 v2 的排名/显著性**不能直接比较**；
- v1 包含 `l4_provider.py`、`l4zsvc_provider.py`、`fda_drugs.txt`、`figure3_replica.py`、`export_store.py`、`chatgpt_template.py`、`trt_sh_isgold.csv`；
- v1 前端有 Figure3、导出、FDA 相关按钮；
- v1 的统计口径与 v2（L1 修正后的带符号 KS）不同，旧结论已按 D1 作废。

### 4.2 后端模块逐文件说明

以下均为 `~/lmna_v2/backend`（GitHub `backend/`）的当前代码。

#### `config.py`

- `DATA_DIR`：`CMAP_DATA_DIR`，默认 `<repo>/cmap_data`；
- `MATRIX_PATH`、`COL_NAMES_PATH`、`ROW_NAMES_PATH`、`SIG_INFO_PATH`、`GENE_INFO_PATH`；
- `N_GENES=12328`、`N_SIGS=473647`；
- `CACHE_DIR`：`LMNA_CACHE_DIR`，默认 `<repo>/cache`；
- `ALGO_VERSION="2"`：算法版本，参与缓存键；
- `MIN_SH_SAMPLES=3`（D3）；
- `KS_THRESHOLD=0.2`、`FDR_THRESHOLD=0.05`（论文模式可设 0.001）；
- `BOOTSTRAP_N=1000`（服务器启动脚本设为 100000）；
- `RANDOM_SEED=42`；
- `MAX_GENES_PER_DIRECTION=50`；
- `FAST_MODE_TOP_N=0`（关闭快速模式）；
- 适用性阈值：`SUITABILITY_MIN_HAIRPINS=2`、`SUITABILITY_MIN_SIG=5`、`SUITABILITY_YELLOW_MIN_SIG=20`、`SUITABILITY_JACCARD_GREEN=0.5`、`SUITABILITY_JACCARD_RED=0.3`、`LOHO_MIN_REMAINING=3`；
- `DEFAULT_TOP_K=50`、`DEFAULT_BOTTOM_K=50`；
- `DRUG_NULL_N=10000`；
- `API_HOST=0.0.0.0`、`API_PORT=8001`（服务器用 `API_PORT=8004` 覆盖）；
- `DATA_PROVIDER=l5`；
- `TASK_TIMEOUT_SEC=7200`；
- `LMNA_ADMIN_TOKEN`（默认空，空时 DELETE 缓存接口一律 403）；
- `LMNA_CORS_ORIGINS`（默认空）；
- `signature_params()`：把 `ALGO_VERSION`、`DATA_PROVIDER`、`KS_THRESHOLD`、`FDR_THRESHOLD`、`BOOTSTRAP_N`、`RANDOM_SEED`、`FAST_MODE_TOP_N`、`MAX_GENES_PER_DIRECTION`、`DRUG_NULL_N` 纳入缓存键。

#### `data_provider.py`

- `IDataProvider` 抽象接口：基因列表、签名矩阵、shRNA/药物元数据、表达矩阵等；
- v2 只实现 `l5` 与 `fixture`；`l3` 是空壳。

#### `l5_provider.py`

- 单例；
- `np.memmap(MATRIX_PATH, dtype='float32', mode='r', shape=(12328, 473647))`；
- 读取 `col_sig_ids.csv`，校验长度 473647；
- **L8 哨兵**：`CHECK_COL_ORDER=True`，若 CSV 恰好是升序（旧文件特征），直接抛 `RuntimeError`，拒绝启动；
- 读取 `row_gene_ids.csv` 建立 gene_id → 行索引；
- 从 `gene_info` 取 `pr_is_lm==1` 的 978 个 landmark 基因；
- `_shrna_df`：`pert_type == 'trt_sh'`；
- `_drug_df`：`pert_type == 'trt_cp'`；
- `get_expression_matrix` 按 chunk 5000 读取，只返回 landmark 行。

#### `drug_median_cache.py`

- 缓存路径：`_drug_median_matrix.v{ALGO_VERSION}.npy`、`_drug_names.v{ALGO_VERSION}.csv`；
- 加载时校验 shape；
- 构建时持有排他锁 + double-check；
- 按药物名分组，`BATCH_SIZE=1000`，对每个药物的所有 signature 取中位数；
- 原子替换；
- 药物中位数矩阵形状 `(978, n_drug)`。

#### `drug_scorer.py`

- `mimic = Σ z(up) − Σ z(down)`；
- `score = −mimic`，**分数越高越逆转**；
- 药物 null：`M=DRUG_NULL_N`、batch、seed；随机签名无放回抽样；
- `p_mimic` 上尾、`p_reversal` 下尾；
- 两个方向分别做 BH，得到 `fdr_mimic`/`fdr_reversal`；
- `null_z = (score − mean(null)) / sd(null)`；
- XSUM：按 FDR 优先、再按 score 方向排序；lof 模式取 `fdr_reversal` 升序 + score 降序；gof 模式取 `fdr_mimic` 升序 + score 升序；
- WTCS：按列排名，权重 `(G+1)-2*rank`；不返回 p/FDR/null_z。

#### `signature_engine.py`

- 秩缓存：`_shrna_rank_matrix.v{ALGO_VERSION}.{n_shrna}.dat` + `.shape.txt`；
- `int16`，带尺寸校验；
- chunk 5000；
- 带符号 KS：`KS>0` 表示上调，`KS<0` 表示下调；
- Bootstrap 无放回，排除目标基因列；
- `p = (count+1)/(B+1)`；
- BH 反向累积最小值；
- 签名过滤：`fdr<FDR_THRESHOLD and abs(ks)>KS_THRESHOLD`；
- `n_sig` 在截断前记录；
- 快速模式取 top N；
- 每方向最多 50 个基因；
- LOHO：`k=max(10, len(up)+len(down))`；
- 返回 `target_median_z` 与 `qc`。

#### `suitability.py`

- 规则 4.4 修订版；
- 注释可选：缺失时显示“未知”，但不改变档位；
- 预检查 hairpin 数；
- LOHO Jaccard；
- 红/黄/绿判档；
- 红档默认不返回药物列表（可通过 `include_red` 恢复）；
- 绿色不代表“数据支持临床”，只是规则档位。

#### `cache_manager.py`

- `exclusive_file_lock`：Unix 用 `fcntl`，Windows 用 `msvcrt`；
- `signature_params_hash`：SHA1 前 10 位；
- `atomic_write_json`；
- `replace_file_with_retry`；
- 签名缓存：`{GENE}_{hash}_signature.json`；
- 药物缓存：`{GENE}_{hash}_{method}_{fast_mode}_{score_mode}_drug_scores.json`；
- `_find_drug_scores_path`：normal 优先于 fast，lof 优先于 gof；
- `clear_gene`：glob 清理；
- `list_cached_genes`。

#### `task_queue.py`

- 去重键：gene + method + mode + score_mode + params_hash；
- `_submit_lock` 线程锁；
- `ProcessPoolExecutor(max_workers=2)`；
- JSON 任务文件；
- `TASK_TIMEOUT_SEC` 心跳超时；
- 启动时清理残留 pending/running；
- `LMNA_TASK_INLINE=1` 时同进程同步执行（测试用）；
- 任务状态：pending/running/completed/failed。

#### `main.py`

- FastAPI 应用；
- CORS 可选，来自 `LMNA_CORS_ORIGINS`；
- 单例 provider/cache/queue；
- 启动清理；
- 路由：
  - `GET /api/health`
  - `GET /api/genes`
  - `GET /api/genes/{gene}/status`
  - `GET /api/genes/{gene}/suitability`
  - `POST /api/genes/{gene}/compute`
  - `GET /api/tasks/{task_id}`
  - `GET /api/tasks`
  - `GET /api/genes/{gene}/signature`
  - `GET /api/genes/{gene}/drugs`
  - `DELETE /api/cache/{gene}`（`X-Admin-Token`，`compare_digest`，未设置 token 时 403）
- StaticFiles mount `/` 放在 API 路由之后；
- `__main__` 直接跑 uvicorn。

#### `provider_factory.py`

- `l5` → `L5Provider`；
- `fixture` → `FixtureProvider`；
- `l3` → `L3Provider`（未实现）。

#### `l3_provider.py`

- 所有方法 `NotImplementedError`；
- 配置为 `DATA_PROVIDER=l3` 会导致启动失败。

#### `fixture_provider.py`

- 读取 `LMNA_FIXTURE_DIR` 下四个文件：
  - `lmna_fixture.npz`
  - `lmna_fixture_sh.tsv`
  - `lmna_fixture_cp.tsv`
  - `lmna_fixture_meta.json`；
- 用于离线测试，不用于生产。

### 4.3 数据层

| 文件 | 维度/大小 | 语义 |
|---|---|---|
| `fast_matrix.npy` | 12328 × 473647，23,356,480,864 bytes | 原始 float32，无 `.npy` 头；列 = GCTX COL，行 = GCTX ROW |
| `col_sig_ids.csv` | 473647 行 | `sig_id` 列表，必须与矩阵列序一致 |
| `row_gene_ids.csv` | 12328 行 | `gene_id` 列表，必须与矩阵行序一致 |
| `GSE92742...gctx` | 473647 × 12328 | 真值来源 |
| `gene_info` | — | `pr_is_lm` 标识 978 landmark |
| `sig_info` | — | `pert_type` 区分 `trt_sh`/`trt_cp` |

L8 修复后的验收数字（部署报告实测）：

- `col_sig_ids.csv`：473647/473647 与 GCTX COL 顺序一致（修复前 3/473647）；
- `row_gene_ids.csv`：12328/12328 与 GCTX ROW 顺序一致（修复前 4/12328）；
- 抽样列校验：5 个 sig_id `max|diff| = 0.000e+00`；
- 药物中位数复核：`min=1.0000 median=1.0000 max=1.0000`，全部 r ≥ 0.99。

注意：

- 旧 `~/cmap/cmap_data` 的 CSV **仍未修复**；旧 cmap 8001 仍在使用旧 CSV；
- 新实例通过 `~/cmap_v2_data` 的实体 CSV 使用修复后的顺序；
- 因此“L8 已修复”只对新实例成立，不能推广到旧 cmap。

### 4.4 缓存结构与版本化

`~/lmna_v2_cache`（实测 369M）：

```text
~/lmna_v2_cache/
├── _shrna_rank_matrix.v2.154993.dat       303,166,308 bytes
├── _shrna_rank_matrix.v2.154993.dat.lock  1 byte
├── _shrna_rank_matrix.v2.154993.shape.txt 10 bytes -> "978,154993"
├── _drug_median_matrix.v2.npy             77,500,760 bytes
├── _drug_median_matrix.v2.npy.lock        1 byte
├── _drug_names.v2.csv                     268,566 bytes
├── signatures/
│   └── TP53_b031a48b8a_signature.json     163,981 bytes
├── drug_scores/
│   └── TP53_b031a48b8a_xsum_normal_lof_drug_scores.json  5,227,185 bytes
└── tasks/
    └── f303296a-1c91-4c.json              28,242 bytes
```

版本化规则：

- `ALGO_VERSION="2"` 出现在文件名中；
- `signature_params_hash` 进入签名/药物缓存名；
- 参数变化（FDR、KS、BOOTSTRAP、DRUG_NULL_N 等）会导致新缓存键，旧缓存不会被误读；
- 所有 JSON 原子写；
- 文件锁防止并发构建；
- 旧版本缓存不会自动删除，需要人工清理。

缓存清理矩阵（重建前必须确认）：

| 变更 | 必须删除 |
|---|---|
| 签名算法/符号/阈值变化 | `signatures/`、`drug_scores/`、`tasks/` |
| 秩矩阵输入变化 | `_shrna_rank_matrix.*` |
| 药物中位数输入变化 | `_drug_median_matrix.*`、`_drug_names.*`、`drug_scores/` |
| 仅前端变化 | 无需删缓存 |
| 仅适用性规则变化 | `signatures/`（qc 存在签名里） |

### 4.5 L0–L8 修复历史

「据 PROGRESS 合并记录」

| 任务 | 合并提交 | 核心内容 | 测试 |
|---|---|---|---|
| L0 | `18685fe` | 测试脚手架 + 夹具；数据源用 LINCS2020 beta Level5 | 脚手架 |
| L1 | `3b799ee` | 带符号 KS 修正；D1/D3 决策；旧结论作废 | 14 项 |
| L2 | `8d367b6` | 缓存版本化、原子写、锁、双重检查 | 128 passed 1 skipped |
| L3 | `f26413f` | 适用性判档、qc、红档屏蔽、mode | 115 passed 1 skipped |
| L4 | `4697806` | 药物级随机签名 null、p/FDR/null_z | 78 passed 1 skipped |
| L5 | `4517e43` | 前端同源、适用性卡片、FDR 列、XSS、换肤 | 129 passed 1 skipped |
| L6 | `c553da0` | 去重、心跳超时、删除缓存鉴权、CORS、L3 空壳 | 68 passed 1 skipped |
| L7 | `f3b4f10` | 设计文档 | 文档 |
| L8 | `7cc2d7b` | 列序/行序对齐、fail-fast 哨兵、重建脚本 | 6 passed；全量 121 passed 1 skipped |

合并顺序与依赖：

- L1 是统计口径的分水岭；
- L8 修正数据层，必须先于可信的缓存重建；
- L2 的版本化保证 L1/L4 参数变化后旧缓存不命中；
- L3/L4 都依赖 L1 的签名口径；
- L5 依赖 L3/L4 的字段；
- L6 是工程加固，可与统计任务并行，但合并时需解决 `task_queue.py`/`cache_manager.py` 冲突。

### 4.6 v1 与 v2 差异清单（含“未移植”）

| 能力 | v1 `~/lmna_app/LMNA` | v2 `~/lmna_v2` | 状态 |
|---|---|---|---|
| 数据提供者 | `l4zsvc`（ZSVC 重建） | `l5`（fast_matrix） | 不同 |
| 数据源 | `/data2/wanggang/camp/level3|4` | `~/cmap_v2_data` | 不同 |
| 签名算法 | 旧口径 | L1 修正后的带符号 KS | 不同，旧结论作废 |
| Bootstrap | 100000 | 100000（启动脚本） | 同量级 |
| FDR | 0.001 | 0.001（启动脚本） | 同 |
| 适用性判档 | 无 | `suitability.py` + `/suitability` | v2 新增 |
| 药物 null/FDR | 无（或旧口径） | `p_reversal/fdr_reversal/p_mimic/fdr_mimic/null_z` | v2 新增 |
| 缓存版本化 | 无 | `ALGO_VERSION=2` + 参数哈希 | v2 新增 |
| 删除缓存鉴权 | 无 | `LMNA_ADMIN_TOKEN` | v2 新增 |
| 任务去重/超时 | 较弱 | L6 去重 + 心跳 + 启动清理 | v2 新增 |
| 测试 | 无 | 14 个测试文件 | v2 新增 |
| **l4zsvc provider** | 有 | **未移植** | 缺口 |
| **l4 provider** | 有 | **未移植** | 缺口 |
| **FDA 药物表/按钮** | `fda_drugs.txt` + 前端 | **未移植** | 缺口 |
| **Figure3 复刻** | `figure3_replica.py` + `/figure3` 路由 | **未移植** | 缺口 |
| **导出（签名 CSV/结果 zip）** | `export_store.py` + `/api/export_data` | **未移植** | 缺口 |
| **ChatGPT 模板** | `chatgpt_template.py` | **未移植** | 缺口 |
| **v1 前端按钮** | Figure3/导出/FDA | 无 | 缺口 |

结论：

- v2 是“正确性/工程性”升级版，但功能覆盖不如 v1；
- 直接把 v1 下线会丢失 l4zsvc、FDA、Figure3、导出等能力；
- 若要合并两套代码，应作为单独移植任务（N7），不要在原任务里顺手改。

### 4.7 纯 HTML 前端（L5）

GitHub `frontend/index.html`（600 行）是 L5 合并后的版本：

- `const API_BASE = ''`，同源部署；FastAPI 在 `/` mount 静态文件；
- Bootstrap 5.3.0 仍从 CDN 加载（`https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css`），D9 未决；
- `esc()` 对所有用户输入/服务端字符串做 HTML 转义，降低 XSS 风险；
- 适用性卡片：显示红/黄/绿档位、hairpin 数、LOHO Jaccard、注释状态；
- 红档默认屏蔽药物列表；
- mode：`lof`/`gof`/`uncertain`；`uncertain` 先算 lof，并把绿色上限压到黄色；
- method：`xsum`/`wtcs`；
- FDR 列：XSUM 根据 mode 显示 `fdr_reversal` 或 `fdr_mimic`，显著性 `<0.05` 加粗；
- `fast_mode` 警告横幅；
- 进度条为不确定进度，不再写死 60%；
- 仅支持浏览器端 JSON/CSV 导出；
- 没有 FDA/Figure3/服务端导出按钮。

线上 8084 的前端不是这个版本：

- 13,299 bytes；
- `API_BASE = 'https://10.39.15.238:8004'`；
- 没有 `suitability`、`fdr_reversal`、`fast_mode`、`esc()`；
- 因此线上用户看不到适用性卡片与 FDR 列。

### 4.8 部署现状：后端 8d367b6、前端仍是 L5 之前版本

「实测（2026-10-18）」

| 组件 | 线上版本 | 证据 |
|---|---|---|
| 后端 | `8d367b6`（L2 合并点，含 L3/L4/L6/L8） | `~/lmna_v2/backend/suitability.py`、`drug_median_cache.py` 存在；路由含 `/suitability`；部署报告写 8d367b6 |
| 前端 | L5 之前 | 13,299 bytes；无适用性/FDR/fast_mode；`API_BASE` 硬编码 8004 |
| 运行参数 | `DATA_PROVIDER=l5`、`CMAP_DATA_DIR=~/cmap_v2_data`、`LMNA_CACHE_DIR=~/lmna_v2_cache`、`BOOTSTRAP_N=100000`、`FDR_THRESHOLD=0.001`、`DRUG_NULL_N=10000`、`FAST_MODE_TOP_N=0`、`LMNA_CORS_ORIGINS=https://10.39.15.238:8084`、`LMNA_ADMIN_TOKEN` 已设置 | `/proc/2797792/environ` 只读核对 |

部署含义：

- 后端已能返回 `suitability` 与 p/FDR 字段，但旧前端不展示；
- 前端跨端口直连 8004，依赖 CORS 白名单；
- 若把前端换成 L5 版本，需要同时改为同源（`API_BASE=''`）或保留 CORS；
- 部署 L5 前端属于 N2 决策。

---

## 5. Easy_R_v2 现状

### 5.1 架构与技术栈

Easy_R_v2 是临床预测模型/统计建模工作台。

| 层 | 实现 |
|---|---|
| 后端 | FastAPI（Python 3.11，`easyr` conda 环境） |
| 前端 | React 18 + Vite 5 + Ant Design + ECharts + DOMPurify |
| 认证 | 自建用户表 + PBKDF2 + HMAC token |
| 报告 | python-docx（Word）、reportlab（PDF） |
| 建模 | scikit-learn、XGBoost、LightGBM、CatBoost、lifelines、SHAP 等 |
| 数据 | 每个用户独立目录；上传 CSV；历史 JSON；报告文件 |
| 部署 | 8008 API + 8092 前端（`serve dist`） |

Python 依赖（`backend/requirements.txt`，均为锁定版本）：

```text
fastapi==0.111.0
uvicorn==0.30.0
pydantic==2.7.0
pandas==2.2.2
numpy==1.26.4
scikit-learn==1.5.0
scipy==1.13.1
statsmodels==0.14.2
matplotlib==3.9.0
seaborn==0.13.2
plotly==5.22.0
xgboost==2.0.3
catboost==1.2.5
boruta-py==0.3.1
lifelines==0.28.0
python-multipart==0.0.9
shap==0.46.0
lightgbm==4.3.0
openpyxl==3.1.5
python-docx==1.1.2
reportlab==4.2.2
```

开发依赖：`pytest==8.3.2`、`httpx==0.27.0`。

### 5.2 E0–E7 修复历史

| 任务 | 合并提交 | 核心内容 | 测试 |
|---|---|---|---|
| E0 | `1b7b809` | 测试脚手架；`EASYR_DATA_DIR` 环境变量化 | 2 passed |
| E1 | `a981bb2` | 报告下载安全（P0）：文件名校验、路径约束、鉴权 | 15 passed |
| E2 | `3b1b49a` | Bootstrap 抽样修正 | 6 passed |
| E3 | `61f4f31` | 统计正确性八项 a–h；X 缺失不再整行删除 | 21 passed |
| E4 | `c6792f6` | 向导状态 | 13 vitest |
| E5 | `b8d9c80` | 安全与健壮性：上传 50MB→413、CORS、并发锁、SVG sanitize | 11 passed |
| E6 | `b3c6ae9` | 前端换肤 Phase 0；matplotlib 配色/中文标题 | pytest 43、vitest 15、build 0 |
| E7 | `34ba9da` | 设计文档 + E7a 警示文案 | 文档 |

当前 main HEAD：`b3c6ae9`（Merge E6）。

### 5.3 认证与密钥

`backend/app/services/auth_service.py`：

- 用户表：`users.json` + 文件锁；
- 密码哈希：PBKDF2-HMAC-SHA256，120,000 次迭代；
- token：base64 payload + HMAC-SHA256 签名；
- token 有效期：7 天；
- 密钥优先级：
  1. `EASYR_AUTH_SECRET` 环境变量；
  2. `EASYR_SECRET_FILE` 指定的文件（默认 `DATA_DIR/../secrets/auth_secret.txt`）；
  3. 自动生成 `token_urlsafe(48)`，写入文件并 `chmod 600`；
- `get_current_user` 通过 `HTTPBearer` 解析。

线上密钥：

- 路径：`~/Easy_R_v2_next_secrets/auth_secret.txt`；
- 权限：`-rw------- keji keji`；
- 大小：64 bytes；
- 内容不在本文记录。

注意：

- E1 上线要求轮换密钥，旧 token 全部失效；
- 当前部署的 `b3c6ae9` 已包含 E1/E5；
- 如果未来重建 `~/Easy_R_v2_next_secrets`，所有用户都需要重新登录。

### 5.4 报告生成与下载安全

`backend/app/routers/report.py`：

- `POST /api/report/generate`：需要登录；`format=word|pdf`；
- `GET /api/report/download/{filename}`：需要登录。

`backend/app/services/report_service.py`：

- 文件名规则：`^report_[0-9]{14}_[A-Za-z0-9_-]{16}\.(docx|pdf)$`；
- 每个用户独立目录：`DATA_DIR/users/<user_id>/reports/`；
- 生成时用 `secrets.token_urlsafe(12)` 生成 16 字符随机段；
- 下载时：
  1. 正则全匹配文件名；
  2. `realpath` 限定在用户 reports 目录内；
  3. 必须是普通文件；
  4. 按扩展名设置 media type；
- 返回 `FileResponse`。

安全结论：

- 防住了路径穿越（`../`）、任意文件读取、跨用户下载；
- 没有“签名 URL”机制，下载依赖 **Authorization Bearer token**（HMAC 签名）；
- 报告文件不会自动过期/清理（**待改进**）；
- Word 报告用 python-docx；PDF 用 reportlab，CJK 字体有回退链；
- E7a 在方法学章节加入固定警示语：“变量筛选在全部数据上完成，内部验证结果偏乐观；内部验证不等于外部验证，结果不能直接用于临床决策。”

### 5.5 CORS、上传限制与前端安全

CORS：

- `EASYR_CORS_ORIGINS`，逗号分隔；
- 默认空；
- 线上 8008 实际设为 `http://10.39.15.238:8092`（因为前端 8092 与 API 8008 不同源）；
- 这与 D2 的“nginx 同源反代、CORS 留空”不一致，是“无 nginx”导致的部署偏差。

上传限制：

- `EASYR_MAX_UPLOAD_MB`，默认 50；
- 线上设为 50；
- 超过限制返回 413；
- 上传文件保存到用户目录，注册到数据集 registry（原子 JSON）。

前端安全：

- DOMPurify + `sanitizeSvg`（E5）；
- 上传/预览/图表路径做转义；
- E5 还加了并发锁，避免同一用户同时写 registry；
- E6 只改主题/样式，没有回退 E5 的安全逻辑（复核结论）。

### 5.6 数据副本与“不自动同步”语义

线上数据：

- 旧 Easy_R：`~/Easy_R/backend/data`；
- 旧 Easy_R_v2：`~/Easy_R_v2/backend/data`；
- 新 Easy_R_v2_next：`~/Easy_R_v2_next_data`（88MB，副本）。

副本内容（实测）：

- `demo.csv`（51,293 bytes）；
- 多个 `upload_*.csv`；
- 历史报告 `report_*.docx`（170KB–922KB）；
- 用户目录/`users.json`。

语义：

- 新实例是“某个时间点的副本”，不是实时同步；
- 老实例新增用户/上传/历史不会出现在新实例；
- 新实例新增数据也不会回到老实例；
- 若决定切换，需要一次性迁移并冻结老实例写入，或做双向同步（不建议）；
- 当前 `Easy_R_v2_next_data` 中没有 `auth_secret.txt`；密钥单独放在 `~/Easy_R_v2_next_secrets`（这是 E1 的改进）。

### 5.7 前端构建

- `frontend/package.json`：React 18、axios、antd、dompurify、echarts、react-router-dom；
- scripts：`dev`、`build`（`tsc && vite build`）、`test`（`vitest run`）；
- `.env.production`：`VITE_API_BASE_URL=/api`（仓库默认，适合 nginx 同源）；
- `api.ts`：baseURL 从 `VITE_API_BASE_URL` 读取，默认 `/api`；Bearer token 从 localStorage 读取；
- 线上构建实际使用 `VITE_API_BASE_URL=http://10.39.15.238:8008/api`（部署报告），产物中已确认包含该地址；
- 因此线上前端是**跨源直连 8008**，不是同源 `/api`；
- 如果未来部署 nginx 同源反代，需要重新构建 dist，把 `VITE_API_BASE_URL` 改回 `/api`。

### 5.8 端口与部署形态

| 实例 | API | 前端 | 数据 | 协议 |
|---|---|---|---|---|
| Easy_R 旧 | 8005 | 8090 | `~/Easy_R/backend/data` | HTTP |
| Easy_R_v2 旧 | 8006 | 8091 | `~/Easy_R_v2/backend/data` | HTTP |
| Easy_R_v2_next | 8008 | 8092 | `~/Easy_R_v2_next_data` | HTTP |

部署脚本 `~/Easy_R_v2_next/start_v2.sh`：

- 激活 `easyr` 环境；
- 设置 `EASYR_DATA_DIR`、`EASYR_SECRET_FILE`、`EASYR_CORS_ORIGINS`、`EASYR_MAX_UPLOAD_MB`；
- 后端 `uvicorn app.main:app --host 0.0.0.0 --port 8008 --workers 1`；
- 前端 `node .../serve dist -p 8092 --cors`；
- PID 文件 `.backend.pid`/`.frontend.pid`；
- 日志 `backend_v2.log`/`frontend_v2.log`。

注意：

- 前端 `serve --cors` 会加宽松 CORS 头，但这只是静态文件服务；API 的 CORS 由 FastAPI 控制；
- 两个进程都只检查 PID 文件，不检查端口占用；
- 没有 HTTPS；
- 没有 systemd；
- 没有日志轮转。

---

## 6. 数据血缘与可复现性

### 6.1 数据来源

当前 cmap/LMNA 共同使用的矩阵来自 **GSE92742 Broad LINCS Level 5 COMPZ MODZ**：

```text
GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx
```

「据代码推断」原因：

- cmap `app/config.py` 的 `GCTX` 文件名就是该 GSE92742 文件；
- LMNA `l5_provider.py` 读取的 `SIG_INFO_PATH`/`GENE_INFO_PATH` 也是 GSE92742 命名；
- `fast_matrix.npy` 的维度与 GCTX `n473647x12328` 完全一致；
- 仓库和部署脚本中没有把 LINCS2020 beta 作为主矩阵的配置。

LINCS2020 beta Level5 的用途：

- L0 夹具构建说明提到“数据源用 LINCS2020 beta Level5”；
- `verify_drug_median.py` 可选 `--beta-dir` 做趋势对照；
- 它不是当前 `fast_matrix.npy` 的来源。

因此：

- 当前线上排名/显著性的真值来源是 **GSE92742 Level5**；
- 不要用 LINCS2020 beta 的数字去核对当前缓存，除非明确只做趋势参考；
- D5（Touchstone 用 GSE92742 还是 LINCS2020）仍未决，属于 Tau 方案 A 的前置决策。

术语解释：

- **L1000**：LINCS 项目用 978 个 landmark 基因的表达来推断全转录组（12328 基因）的方法；
- **Level 5**：LINCS 官方聚合后的 z-score 数据；
- **MODZ**：聚合方法（mode of z-scores）；
- **GCTX**：Broad 的 HDF5 格式，包含矩阵与行列元数据；
- **signature（签名）**：一次扰动（药物/基因敲低）引起的基因表达变化模式；
- **landmark genes**：978 个直接测量的基因；
- **trt_cp**：compound（化合物/药物）处理；
- **trt_sh**：shRNA 敲低处理。

### 6.2 `fast_matrix.npy` 与 GCTX 的真值关系

维度与字节数：

```text
12328 × 473647 × 4 bytes (float32) = 23,356,480,864 bytes
```

实测：

- `~/cmap/cmap_data/fast_matrix.npy` 大小 23,356,480,864 bytes；
- `~/cmap_v2_data/fast_matrix.npy` 是指向它的软链接（41 bytes 的符号链接）；
- 矩阵是**原始 float32，没有 `.npy` 头**，因此不能直接 `np.load`，必须按 shape memmap。

语义：

- 列顺序 = GCTX 的 COL 顺序；
- 行顺序 = GCTX 的 ROW 顺序；
- `fast_matrix[:, k]` 对应 GCTX 第 k 列（一个 signature）；
- `fast_matrix[g, :]` 对应 GCTX 第 g 行（一个基因）；
- 列名由 `col_sig_ids.csv` 提供，行名由 `row_gene_ids.csv` 提供；
- 如果 CSV 顺序与矩阵不一致，按名字取数会**静默读到错误的列/行**，这是 L8 修复的核心问题。

L8 抽样验证：

- 取 5 个 `sig_id`；
- 比较 `fast_matrix[:, k]` 与 `GCTX[k, :]`；
- `max|diff| = 0.000e+00`；
- 说明修复后的列序逐元素一致。

### 6.3 列序/行序修复脚本

脚本：`scripts/fix_col_names.py`（234 行）。

设计原则：

- 只读取 GCTX 的 `0/META/COL/id` 与 `0/META/ROW/id`；
- 不把 23GB 矩阵读入内存；
- 支持 `--check` 只检查；
- 支持 `--in-place` 原地替换（自动备份 `.bak-<timestamp>`）；
- 支持 `--fix-rows` 同时修行序；
- 支持 `--verify N` 抽样列校验；
- 原子写；
- 遇到重复 ID 或抽样不一致直接退出。

推荐用法（部署窗口，人工执行）：

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate cmap
cd ~/lmna_v2

# 1) 只检查，不写文件
python scripts/fix_col_names.py --data-dir ~/cmap_v2_data --check

# 2) 生成修复文件，人工确认
python scripts/fix_col_names.py --data-dir ~/cmap_v2_data

# 3) 原地替换 + 修行序（自动备份）
python scripts/fix_col_names.py --data-dir ~/cmap_v2_data --in-place --fix-rows
```

注意：

- 该脚本的默认 `--data-dir` 是 `~/cmap/cmap_data`，会改到旧目录；新实例必须显式传 `~/cmap_v2_data`；
- 脚本本身不重建缓存；修完 CSV 后必须按 6.4 节清理并重建；
- 旧 `~/cmap/cmap_data` 的 CSV 未修，旧 cmap 仍可能读错列；
- 不要在服务运行期间反复替换数据文件。

本次实测的 CSV 校验和：

| 文件 | 大小 | MD5 | 状态 |
|---|---:|---|---|
| `~/cmap_v2_data/col_sig_ids.csv` | 17,433,427 | `b7d0b45df6ad1db07b519103b2641984` | 已修（GCTX COL 顺序） |
| `~/cmap_v2_data/row_gene_ids.csv` | 67,518 | `4aa1c61af86dc224e59b0228f046b2d6` | 已修（GCTX ROW 顺序） |
| `~/cmap/cmap_data/col_sig_ids.csv` | 17,907,075 | `a55b1e318fb1267ef5c7e35efeac7c49` | 旧序，未修 |
| `~/cmap/cmap_data/row_gene_ids.csv` | 79,847 | `1365df63dd2decb0161cef5925a9ee07` | 旧序，未修 |

验收数字：

- 列：473647/473647 同位置一致（修复前 3/473647）；
- 行：12328/12328 同位置一致（修复前 4/12328）；
- 抽样列：`max|diff| = 0.000e+00`；
- 药物中位数复核：`min=1.0000 median=1.0000 max=1.0000`。

### 6.4 缓存重建手册

以下步骤是**写操作**，只能在部署窗口由人执行。本文档编写期间未执行。

#### LMNA v2 缓存重建

前置条件：

- CSV 已修复（6.3）；
- 服务可停；
- 磁盘有约 400MB 以上余量；
- conda 环境 `cmap` 可用。

步骤：

```bash
# 1) 停服务（注意进程池子进程）
bash ~/lmna_v2/stop_v2.sh
ss -ltnp | grep 8004 || echo "8004 已释放"

# 2) 备份旧缓存（可选，但建议）
mv ~/lmna_v2_cache ~/lmna_v2_cache.bak.$(date +%Y%m%d-%H%M%S)

# 3) 重建目录
mkdir -p ~/lmna_v2_cache/signatures ~/lmna_v2_cache/drug_scores ~/lmna_v2_cache/tasks

# 4) 启动服务
bash ~/lmna_v2/start_v2.sh

# 5) 触发预热（TP53）
curl -k -s -X POST https://127.0.0.1:8004/api/genes/TP53/compute \
  -H 'Content-Type: application/json' \
  -d '{"method":"xsum","mode":"lof"}'

# 6) 轮询任务
curl -k -s https://127.0.0.1:8004/api/tasks/<task_id>
```

重建内容：

| 文件 | 触发时机 | 约大小 |
|---|---|---|
| `_shrna_rank_matrix.v2.154993.dat` | 首次签名计算 | 303MB |
| `_drug_median_matrix.v2.npy` | 首次药物打分 | 77.5MB |
| `_drug_names.v2.csv` | 同上 | 269KB |
| `signatures/TP53_*.json` | TP53 签名 | 164KB |
| `drug_scores/TP53_*.json` | TP53 筛药 | 5.2MB |
| `tasks/*.json` | 任务状态 | 几十KB |

时间：

- 部署报告实测 TP53 预热约 6 分钟；
- 主要耗时在秩矩阵构建与 100000 次 bootstrap；
- 药物 null `M=10000` 也占一部分；
- 具体时间随 CPU/磁盘负载变化，**待实测**更细的分段耗时。

验收：

```bash
# 任务状态
curl -k -s https://127.0.0.1:8004/api/genes/TP53/signature | head
curl -k -s 'https://127.0.0.1:8004/api/genes/TP53/drugs?method=xsum&mode=lof' | head

# 缓存文件
ls -lh ~/lmna_v2_cache
cat ~/lmna_v2_cache/_shrna_rank_matrix.v2.154993.shape.txt
```

预期：

- `n_sig=43`（up 19 / down 24）；
- `qc.grade=yellow`（因为 `gene_annotations.tsv` 未配置）；
- `fdr_reversal≈0.99`（DRUG_NULL_N=10000 的分辨率限制，不是故障）。

#### cmap_v2 药物中位数矩阵

C3 部署时需要：

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate cmap
cd ~/cmap_v2

# 复用 LMNA 的 v2 药物中位数矩阵（推荐，省时间）
export CMAP_DATA_DIR=~/cmap_v2_data
python scripts/build_drug_median.py --from-lmna ~/lmna_v2_cache

# 或从 GCTX 重新构建（较慢）
python scripts/build_drug_median.py --data-dir ~/cmap_v2_data
```

输出（默认写到 `CMAP_DATA_DIR`）：

- `drug_median_lm.npy`（978 × n_drug，标准 `.npy`）；
- `drug_median_names.csv`；
- `drug_median_lm_gene_ids.csv`。

注意：

- `--from-lmna` 读取 `_drug_median_matrix.v2.npy` 与 `_drug_names.v2.csv`；
- 若要保证 cmap 与 LMNA 的药物集合一致，优先用 `--from-lmna`；
- 构建后需确认 `n_drug` 与生产规模（约 19811）一致；
- 线上 8007 目前没有该脚本与矩阵，部署 C3 时一并处理。

#### 旧 cmap 缓存/数据

旧 cmap 8001 使用旧 CSV，**不要**在不升级代码的情况下只替换 CSV：

- 旧代码没有 L8 哨兵，替换后可能“看起来正常”但行为改变；
- 旧实例与新实例共享大矩阵，替换 CSV 会影响两个实例；
- 正确做法是：先升级旧实例代码到含 L8 的版本，或在维护窗口统一切换。

### 6.5 夹具与环境变量

#### LMNA 夹具

`fixture_provider.py` 读取：

```text
$LMNA_FIXTURE_DIR/
├── lmna_fixture.npz
├── lmna_fixture_sh.tsv
├── lmna_fixture_cp.tsv
└── lmna_fixture_meta.json
```

用途：

- 离线测试；
- 不依赖 23GB 矩阵；
- CI 未配置，因此目前只在本地/agent 环境使用。

#### 环境变量总表

LMNA：

| 变量 | 默认 | 说明 |
|---|---|---|
| `CMAP_DATA_DIR` | `<repo>/cmap_data` | 数据目录 |
| `LMNA_CACHE_DIR` | `<repo>/cache` | 缓存目录 |
| `DATA_PROVIDER` | `l5` | `l5`/`fixture`；`l3` 未实现 |
| `ALGO_VERSION` | 代码常量 `2` | 缓存版本 |
| `MIN_SH_SAMPLES` | 3 | 最少 shRNA 样本 |
| `KS_THRESHOLD` | 0.2 | KS 阈值 |
| `FDR_THRESHOLD` | 0.05 | 签名 BH-FDR 阈值 |
| `BOOTSTRAP_N` | 1000 | bootstrap 次数 |
| `MAX_GENES_PER_DIRECTION` | 50 | 每方向基因上限 |
| `FAST_MODE_TOP_N` | 0 | 快速模式 |
| `DRUG_NULL_N` | 10000 | 药物 null 次数 |
| `TASK_TIMEOUT_SEC` | 7200 | 任务超时 |
| `LMNA_ADMIN_TOKEN` | 空 | 删除缓存令牌 |
| `LMNA_CORS_ORIGINS` | 空 | CORS 白名单 |
| `GENE_ANNOTATIONS_PATH` | `<data>/gene_annotations.tsv` | D4 注释表 |
| `LMNA_FIXTURE_DIR` | — | 夹具目录 |
| `LMNA_TASK_INLINE` | — | 设为 1 时同步执行（测试） |

cmap：

| 变量 | 默认 | 说明 |
|---|---|---|
| `CMAP_DATA_DIR` | `<repo>/cmap_data` | 数据目录 |
| `CMAP_TEMP_DIR` | `<repo>/temp` | 临时目录 |
| `CMAP_N_GENES` | 12328 | 矩阵行数（测试可覆盖） |
| `CMAP_N_SIGS` | 473647 | 矩阵列数（测试可覆盖） |
| `CMAP_CSV_TOP_N_MAX` | 150 | CSV topN 上限 |
| `CMAP_CORS_ORIGINS` | 空 | CORS 白名单 |
| `CMAP_TOUCHSTONE_DIR` | `<repo>/touchstone_data` | Touchstone 数据 |
| `CMAP_NULL_N` | 10000（C3 代码） | null 次数；线上无此代码 |
| `CMAP_NULL_SEED` | 0（C3 代码） | null 随机种子 |
| `CMAP_NULL_BATCH` | 500（C3 代码） | null 批大小 |
| `CMAP_NULL_MIN_GENES` | 10（C3 代码） | 最少可用 landmark 基因数 |
| `CMAP_DRUG_MEDIAN_MATRIX` | `<data>/drug_median_lm.npy` | 药物中位数矩阵路径 |
| `CMAP_DRUG_MEDIAN_NAMES` | `<data>/drug_median_names.csv` | 药物名路径 |
| `CMAP_DRUG_MEDIAN_GENE_IDS` | `<data>/drug_median_lm_gene_ids.csv` | 行基因 ID 路径 |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | 监听地址/端口 |

Easy_R：

| 变量 | 默认 | 说明 |
|---|---|---|
| `EASYR_DATA_DIR` | `backend/data` | 数据目录 |
| `EASYR_DEMO_PATH` | `demo.csv` | 演示数据 |
| `EASYR_AUTH_SECRET` | — | 认证密钥（优先级最高） |
| `EASYR_SECRET_FILE` | `DATA_DIR/../secrets/auth_secret.txt` | 密钥文件 |
| `EASYR_CORS_ORIGINS` | 空 | CORS 白名单 |
| `EASYR_MAX_UPLOAD_MB` | 50 | 上传上限 |

### 6.6 校验和、快照与当前缺口

已有：

- CSV 的 MD5 已记录（6.3）；
- 部署报告记录了 L8 验收数字；
- 证书日期/CN 已记录；
- 缓存文件大小已记录。

缺口：

1. **没有 `fast_matrix.npy` 的校验和/大小清单**。23GB 文件做一次 MD5 耗时很长，但不做就无法发现静默损坏。
2. **没有 GCTX 的校验和**。
3. **没有数据 manifest**（文件名、大小、MD5、生成时间、生成命令、数据源版本）。
4. **没有快照机制**：`~/cmap_v2_data` 的 CSV 有 `.bak-*`，但没有版本化命名/保留策略。
5. **没有启动自检**：服务启动时不会校验 CSV 行数/顺序/矩阵尺寸（L8 哨兵只检查“是否升序”这一种旧文件特征，不是完整校验）。
6. **没有缓存清单**：不知道哪些缓存属于哪个参数组合，只能靠文件名猜。

建议（见 11.5）：

- 建立 `data_manifest.json`，记录每个数据文件的 `path/size/md5/mtime/source/command`；
- 启动时做轻量自检（行数、shape、首/中/末 ID 抽样）；
- 重数据（23GB）用 `sha256sum` 分块或 `xxh3` 快速校验；
- 每次部署把 manifest 一起归档。

---

## 7. 安全现状与缺口

### 7.1 认证矩阵

| 系统/接口 | 认证 | 授权 | 现状 |
|---|---|---|---|
| cmap 全部 API | 无 | 无 | 内网开放；任何人可调用全库扫描/导出 |
| cmap 前端 | 无 | 无 | 同源 8007；旧 8081 |
| LMNA 查询/计算 API | 无 | 无 | 内网开放 |
| LMNA `DELETE /api/cache/{gene}` | `X-Admin-Token` | 单一管理员令牌 | 已启用（L6） |
| LMNA 前端 | 无 | 无 | 内网开放 |
| Easy_R 业务 API | Bearer token | 用户级 | 已启用 |
| Easy_R 报告下载 | Bearer token | 用户级 + 文件名校验 | 已启用（E1） |
| Easy_R 注册/登录 | 用户名密码 | — | 已启用 |
| 门户 8888 | 无 | 无 | 仅导航 |
| 服务器 SSH | 密钥 | `keji` 用户 | 已启用 |

结论：

- 只有 Easy_R 有完整用户体系；
- cmap/LMNA 是“内网可信”模型，没有登录、没有速率限制、没有审计；
- 一旦服务器端口暴露到更大网络，任何人都可以跑全库扫描、消耗 CPU、导出数据；
- LMNA 的管理令牌只保护删除缓存，不保护计算/查询。

### 7.2 密钥与文件权限

| 密钥/文件 | 路径 | 权限 | 说明 |
|---|---|---|---|
| cmap 私钥 | `~/cmap/certs/cmap.key` | 0600 | 自签证书私钥 |
| cmap_v2 私钥 | `~/cmap_v2/certs/cmap.key` | 0600 | 自签证书私钥 |
| LMNA v1 私钥 | `~/lmna_app/LMNA/backend/lmna.key`、`frontend/lmna.key` | 0600 | 自签证书私钥 |
| LMNA v2 私钥 | `~/lmna_v2/backend/lmna.key`、`frontend/lmna.key` | 0600 | 自签证书私钥 |
| LMNA 管理令牌 | `~/lmna_v2/.admin_token` | 0600（实测目录项） | 不记录内容 |
| Easy_R 认证密钥 | `~/Easy_R_v2_next_secrets/auth_secret.txt` | 0600 | 64 bytes，不记录内容 |
| Easy_R 旧密钥 | `~/Easy_R/backend/data/auth_secret.txt` | 0664（实测） | 旧实例，权限偏宽 |
| Easy_R_v2 旧密钥 | `~/Easy_R_v2/backend/data/auth_secret.txt` | 0664（实测） | 旧实例，权限偏宽 |

风险：

- 旧 Easy_R 的 `auth_secret.txt` 是 0664，同组用户可读；建议改为 0600 或迁移到 secrets 目录；
- 私钥虽然 0600，但服务器是多租户，root 及其他高权限用户仍可读；
- 没有密钥轮换记录/到期提醒；
- 证书私钥与证书放在项目目录内，备份/打包时容易误带；`.gitignore` 已忽略 `*.key`，但仍需人工注意。

### 7.3 CORS 白名单

| 实例 | 运行值 | 评价 |
|---|---|---|
| cmap_v2 8007 | 空（同源） | 正确 |
| cmap 旧 8001 | 未知/默认 | 旧代码，建议核对 |
| LMNA v2 8004 | `https://10.39.15.238:8084` | 因为前端跨端口，必须开；与 D2 同源目标不一致 |
| Easy_R_v2_next 8008 | `http://10.39.15.238:8092` | 因为前端跨端口，必须开；与 D2 同源目标不一致 |
| LMNA v1 8003 | 未知 | 旧代码 |

评价：

- CORS 白名单本身是收紧的（不是 `*`），比完全开放好；
- 但“跨端口 + 自签证书”是被动选择，不是设计目标；
- 如果上 nginx 同源反代，应把 CORS 清空，减少攻击面。

### 7.4 自签证书

- CN=10.39.15.238，有效期至 2036-06-16；
- 所有 HTTPS 实例共用同一 CN（不同文件）；
- 浏览器会提示不受信任；
- 没有证书链/OCSP/自动续期；
- Easy_R 完全没有 HTTPS。

风险：

- 用户可能养成“忽略证书警告”的习惯，降低钓鱼防护；
- 明文 HTTP 下 token/密码/患者数据可被内网嗅探；
- 没有 HSTS。

建议：

- 内网有 DNS 时，用内部 CA 签发域名证书；
- 或统一用 Caddy/nginx 做 TLS 终止 + 自签 CA 分发；
- Easy_R 至少加 HTTPS（N5）。

### 7.5 上传限制

Easy_R：

- 默认 50MB；
- 超限 413；
- 文件保存到用户目录；
- 文件名/路径需继续审计（E5 已做一部分）。

cmap/LMNA：

- cmap CSV 上传有解析限制与 topN 限制；
- LMNA 没有文件上传（只输入基因名）；
- 没有统一的请求体大小限制/速率限制。

风险：

- cmap 的 CSV 解析可能被超大文件拖垮；
- 没有并发配额，单个用户可占满线程；
- 没有病毒扫描（内网科研场景可接受，但需知晓）。

### 7.6 报告下载安全

见 5.4。结论：

- 已修复路径穿越与跨用户下载；
- 依赖 Bearer token，不是签名 URL；
- 文件名随机段 16 字符，难以枚举；
- 报告不过期、不自动清理；
- 报告内容可能含患者数据，需按数据红线管理。

### 7.7 LMNA 删除缓存鉴权

代码：

```python
if not config.LMNA_ADMIN_TOKEN:
    raise HTTPException(status_code=403, detail="未配置管理员令牌")
if not secrets.compare_digest(token, config.LMNA_ADMIN_TOKEN):
    raise HTTPException(status_code=403, detail="管理员令牌无效")
```

线上：

- `~/lmna_v2/.admin_token` 存在；
- 启动脚本在 `LMNA_ADMIN_TOKEN` 未设置时自动读取该文件；
- 实测运行进程环境中有 `LMNA_ADMIN_TOKEN`（只确认存在，未读取内容）。

建议：

- 令牌长度 ≥32 随机字节；
- 定期轮换；
- 不要把令牌写进 shell history/文档；
- 未来若加统一认证，删除接口应改为角色权限，而不是单一令牌。

### 7.8 多租户边界

见 1.8。安全视角补充：

- 同一台机器上其他用户的服务与本项目共享网络命名空间；
- 任何监听 `0.0.0.0` 的端口都对内网开放；
- 没有防火墙规则（至少本次未检查/未发现项目级防火墙）；
- 没有容器隔离，进程可以读取同用户/同组文件；
- 建议至少做：端口白名单、fail2ban/SSH 限制、日志审计、密钥目录 0700。

### 7.9 安全缺口清单

| ID | 缺口 | 影响 | 优先级 |
|---|---|---|---|
| S1 | cmap/LMNA 无认证 | 内网任何人可调用/消耗资源/导出 | P1 |
| S2 | Easy_R 明文 HTTP | 密码/token/患者数据可嗅探 | P1 |
| S3 | 无统一入口/无 nginx | 无法集中 TLS/认证/限流 | P1 |
| S4 | 旧 Easy_R 密钥 0664 | 同组用户可读 | P2 |
| S5 | 无速率限制 | 单用户可拖垮服务 | P1 |
| S6 | 无审计日志 | 无法追溯谁跑了什么 | P2 |
| S7 | 无密钥轮换 | 长期泄露风险 | P2 |
| S8 | 无上传病毒/内容扫描 | 恶意文件风险 | P2 |
| S9 | 报告不过期 | 患者数据长期留存 | P2 |
| S10 | 自签证书 + 忽略警告习惯 | 中间人风险 | P2 |
| S11 | 多租户无隔离 | 横向影响/数据泄露 | P1 |
| S12 | 旧 cmap CSV 未修 | 结果错误，且可能被当作“正常” | P0（正确性） |

---

## 8. 测试与 CI 现状

### 8.1 三仓库测试脚手架

「实测（2026-10-18，`find` + `grep 'def test_'`）」

| 仓库 | 测试文件 | `def test_` 数量 | 最近报告通过数 | 备注 |
|---|---|---:|---:|---|
| LMNA | 14 个（`backend/tests/test_*.py`） | 108 | 129 passed 1 skipped | 参数化后数量增加；含 1 个既有 skip（D3 Table S1 缺失） |
| cmap | 8 个（`tests/test_*.py`） | 39 | 39 passed 1 skipped | C3 合并后 |
| Easy_R_v2 | 6 个 pytest + 2 个 vitest | 39（py） | 43 passed；vitest 15 passed | E6 报告；build 退出码 0 |

LMNA 测试文件：

```text
backend/tests/test_L2_cache_versioning.py
backend/tests/test_api_hardening.py
backend/tests/test_api_health.py
backend/tests/test_core_pure.py
backend/tests/test_drug_null.py
backend/tests/test_fixture_provider.py
backend/tests/test_fixture_regression.py
backend/tests/test_l8_col_order.py
backend/tests/test_provider_l3.py
backend/tests/test_signature_fixture.py
backend/tests/test_signature_math.py
backend/tests/test_suitability.py
backend/tests/test_task_hardening.py
backend/tests/test_task_inline.py
```

cmap 测试文件：

```text
tests/test_async_deploy.py
tests/test_build_drug_median.py
tests/test_config_defaults.py
tests/test_health.py
tests/test_null_calibrator.py
tests/test_search.py
tests/test_tau_null_integration.py
tests/test_topk.py
```

Easy_R 测试文件：

```text
backend/tests/test_bootstrap.py
backend/tests/test_e5_hardening.py
backend/tests/test_plot_style.py
backend/tests/test_report_security.py
backend/tests/test_smoke.py
backend/tests/test_stats_correctness.py
frontend/src/context/WizardContext.test.ts
frontend/src/utils/sanitizeSvg.test.ts
```

### 8.2 测试命令

LMNA：

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate cmap
cd ~/lmna_v2/backend
python -m pytest -q
```

cmap：

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate cmap
cd ~/cmap_v2
python -m pytest -q
```

Easy_R：

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate easyr
cd ~/Easy_R_v2_next/backend
pytest -q

cd ~/Easy_R_v2_next/frontend
npm test -- --run
npm run build
```

注意：

- 测试可能使用合成小矩阵/夹具，不能替代生产规模验证；
- Easy_R 的 `npm run build` 会跑 `tsc && vite build`，需要 Node 20（服务器 `~/.nvm/versions/node/v20.20.2/bin`）；
- 测试通过不等于部署正确，仍需健康检查与业务抽样。

### 8.3 CI 现状

「实测：三个仓库均无 `.github` 目录」

结论：

- 没有 GitHub Actions；
- 没有自动测试、自动构建、自动部署；
- 没有 PR 检查；
- 所有测试都是本地/agent 手动执行；
- 合并质量依赖人工复核。

风险：

- 回归可能被漏掉；
- 合并冲突解决后没有自动验证；
- 前端构建失败可能到部署时才发现；
- 测试数量虽多，但没有“必须通过才能合并”的门禁。

### 8.4 覆盖率估计与依据

现状：

- 三个仓库都没有 `coverage.py`/`pytest-cov` 配置；
- 没有覆盖率报告；
- 因此**无法给出可信的覆盖率数字**。

粗略估计（仅作方向，不作验收）：

| 仓库 | 估计 | 依据 |
|---|---|---|
| LMNA | 中（核心纯函数覆盖较好，API/进程池/真实数据路径覆盖一般） | 14 个测试文件覆盖签名数学、缓存、任务、适用性、L8、fixture；但生产 L5 路径依赖夹具 |
| cmap | 中（C1/C2/C3/C4 都有专项测试） | 8 个文件覆盖 topN、异步部署、null、健康、搜索；全库真实矩阵只做小规模 |
| Easy_R | 中（安全/统计/前端状态有专项） | 6 个 pytest + 2 个 vitest；ML 算法分支多，难以全覆盖 |

建议：

- 加 `pytest-cov`，先在 CI 中设一个低阈值（如 50%）防止倒退；
- 对核心统计函数（签名 KS、BH、null、打分）要求更高覆盖；
- 前端加 `vitest --coverage`；
- 覆盖率不是目标，**关键路径的断言质量**更重要。

---

## 9. 性能现状与瓶颈

### 9.1 LMNA 预热与缓存

实测：

- TP53 预热约 6 分钟；
- 产物：
  - 秩矩阵 303,166,308 bytes；
  - shape `978,154993`；
  - 药物中位数 77,500,760 bytes；
  - 药物名 268,566 bytes；
  - TP53 签名 163,981 bytes；
  - TP53 药物结果 5,227,185 bytes；
- `n_sig=43`（up 19 / down 24）；
- `qc.grade=yellow`；
- `fdr_reversal≈0.99`。

耗时构成（据代码推断）：

1. 读取 154,993 个 shRNA 签名的表达/秩数据；
2. 构建 978 × 154,993 的秩矩阵（首次）；
3. 对 TP53 的 hairpin 做带符号 KS；
4. 100,000 次 bootstrap（服务器 `BOOTSTRAP_N=100000`）；
5. BH 校正与签名过滤；
6. 构建/读取药物中位数矩阵；
7. 对约 19,811 个药物做 XSUM；
8. 10,000 次随机签名 null + BH。

优化空间：

- 秩矩阵只构建一次，后续复用；
- 药物中位数矩阵只构建一次；
- bootstrap 次数是最大耗时项，可按场景降为 10,000（但会影响 FDR 分辨率）；
- 签名缓存命中后只做药物打分，通常秒级到分钟级；
- 多基因并发受 `ProcessPoolExecutor(max_workers=2)` 限制。

### 9.2 cmap 的 `-w 1` 阻塞模型

现状：

- 单 worker + 8 线程；
- Tau 全库扫描在后台线程中执行；
- 扫描 473,647 个签名，计算 WTCS；
- 后处理做 NCS、药物聚合、Tau；
- 请求线程与计算线程共享 GIL（NumPy 释放 GIL 的部分可并行）。

风险：

- 多个 Tau 任务同时跑会争抢 CPU/内存；
- 没有任务队列上限/公平调度；
- 单个大请求可能让其他请求变慢；
- 503/超时策略不明确。

建议：

- 对 Tau 任务做并发上限（如 1–2 个）；
- 任务排队 + 进度查询；
- 大任务放独立进程/独立服务；
- 监控队列长度与耗时。

### 9.3 memmap 冷读与 chunk

- `fast_matrix.npy` 23.36GB；
- `np.memmap` 零拷贝，首次访问触发页缓存加载；
- cmap 批量 chunk 10000；
- LMNA chunk 5000；
- 冷读性能取决于磁盘（未实测）；
- 热读（页缓存命中）接近内存带宽；
- 多进程会各自持有映射，但页缓存共享；
- `-w 4` 旧实例可能造成更多重复扫描/内存压力。

待实测：

- 冷读扫描 473,647 列耗时；
- 随机列 vs 顺序列的性能差异；
- 页缓存命中率；
- 磁盘 IOPS/吞吐。

### 9.4 各层缓存策略

| 层 | 缓存 | 失效条件 | 存储 |
|---|---|---|---|
| cmap 元数据 | 进程内 index | 重启 | 内存 |
| cmap 任务 | JSON job 文件 | 启动清理 pending/running | `CMAP_TEMP_DIR` |
| cmap 导出 | token + 临时文件 | token 消费/过期（代码） | `CMAP_TEMP_DIR` |
| LMNA 签名 | `{GENE}_{hash}_signature.json` | 参数哈希变化/手动删 | `~/lmna_v2_cache/signatures` |
| LMNA 药物 | `{GENE}_{hash}_{method}_{fast}_{mode}_drug_scores.json` | 参数/方法/模式变化/手动删 | `~/lmna_v2_cache/drug_scores` |
| LMNA 秩矩阵 | `_shrna_rank_matrix.v2.{n}.dat` | ALGO_VERSION/输入变化 | `~/lmna_v2_cache` |
| LMNA 药物中位数 | `_drug_median_matrix.v2.npy` | 数据/版本变化 | `~/lmna_v2_cache` |
| Easy_R 数据 | 用户目录 JSON/CSV | 用户操作 | `~/Easy_R_v2_next_data` |
| Easy_R 报告 | docx/pdf | 手动清理 | 用户 reports 目录 |

问题：

- 没有统一缓存大小上限；
- 没有 TTL；
- 没有淘汰策略；
- 没有缓存命中率指标；
- 旧缓存不会自动清理。

### 9.5 已测性能数据

| 指标 | 数值 | 来源/条件 |
|---|---|---|
| cmap C3 null 校准 | 1.416s，峰值 206.8MB | 978 × 19,811，M=10000 |
| cmap health | 12.6ms | 本机 curl，2026-10-18 |
| cmap 旧 health | 14.0ms | 本机 curl |
| LMNA health | 100.4ms | 本机 curl（含 TLS） |
| Easy_R health | 2.6ms | 本机 curl |
| 门户 8888 | 1.9ms | 本机 curl |
| LMNA TP53 预热 | 约 6 分钟 | 部署报告 |
| LMNA 秩矩阵 | 303MB / 154,993 列 | 实测文件 |
| LMNA 药物中位数 | 77.5MB / 978 × 19,811 | 实测文件 |
| LMNA 药物结果 | 5.2MB / TP53 | 实测文件 |
| 全库 WTCS 扫描 | 未实测 | 待补 |
| memmap 冷读 | 未实测 | 待补 |
| Easy_R 建模耗时 | 未实测 | 待补 |

注意：health 耗时包含 TLS 握手差异，不能横向比较业务性能。

### 9.6 瓶颈排序

按当前证据，瓶颈优先级：

1. **cmap 全库扫描**：473,647 签名 × 多药物聚合，CPU/IO 密集；并发能力弱；
2. **LMNA bootstrap**：100,000 次，单基因约 6 分钟；多基因排队；
3. **memmap 冷读**：23GB，首次扫描受磁盘限制；
4. **单 worker 架构**：故障隔离差，长任务互相影响；
5. **无缓存淘汰/监控**：缓存增长不可控；
6. **多租户资源竞争**：其他项目同时跑任务时性能波动。

---

## 10. 已知问题与技术债台账

严重度定义：

- **P0**：影响结果正确性或数据安全，必须优先处理；
- **P1**：影响可用性、可维护性、安全性，应尽快处理；
- **P2**：体验/工程卫生问题，可排期处理；
- **P3**：长期演进项。

| ID | 现象 | 影响 | 来源/证据 | 严重度 |
|---|---|---|---|---|
| I1 | 线上 cmap_v2 是 `0a02aa3`，不含 C3 | 8007 没有 p/FDR/null_z；用户以为 C3 已上线 | 实测 find/grep + 部署报告 | P1 |
| I2 | 线上 LMNA 前端是 L5 之前版本（13,299 bytes） | 无适用性卡片、无 FDR 列、无 fast 警告、无 XSS 转义 | 实测 grep/文件大小 | P1 |
| I3 | 8003/8004 多个 PID 被误认为“重复服务” | 可能误杀进程池 worker，导致任务失败/端口残留 | 实测父子 PID/cmdline/cwd | P1（认知） |
| I4 | 没有 nginx；D2 同源反代未落地 | 跨端口、自签证书、CORS 被动开放、无统一 TLS | `ls /etc/nginx` 不存在 | P1 |
| I5 | 新实例未加入 `portal-stack.service`/`restart_all.sh` | 服务器重启后新实例不自动恢复 | 实测 unit/脚本 | P1 |
| I6 | 多租户共享服务器，无隔离 | 资源竞争、误杀、横向数据风险 | `ss`/`ps` 实测 | P1 |
| I7 | `DRUG_NULL_N=10000` 导致 `fdr_reversal≈0.99` | 药物级 FDR 几乎不可用 | 部署报告 + L4 文档 | P1 |
| I8 | C3 生产 BH 家族约 19,811，FDR 下限≈1.98 | 默认 M 下无法得到 FDR<0.05 的显著药物 | C3/PROGRESS | P1 |
| I9 | `gene_annotations.tsv` 缺失（D4） | 适用性判档第一层“未知”；TP53 显示 yellow | 配置默认路径 + 部署报告 | P2 |
| I10 | l4zsvc/FDA/Figure3/export 未移植到 v2 | v2 功能少于 v1；不能直接下线 v1 | v1/v2 文件清单 | P1 |
| I11 | Easy_R 全部实例无 HTTPS | 密码/token/患者数据明文传输 | `ss` + 启动脚本 | P1 |
| I12 | `verify_drug_median.py` 仍读旧缓存名 | 复核脚本找不到 `.v2` 文件；本次用软链绕过 | 脚本第 42–43 行 | P2 |
| I13 | 旧 `~/cmap/cmap_data` CSV 未修 | 旧 cmap 8001 可能按错误列序取数 | MD5 对比 | P0 |
| I14 | 旧 cmap 代码更旧（无 C1/C2/C3，`-w 4`） | 旧实例行为与新实例不一致 | 实测 config/start/进程 | P1 |
| I15 | D7 记录“默认500，可改150”，代码默认 150 | 决策与实现不一致，导出条数可能不符预期 | PROGRESS vs `app/config.py` | P2 |
| I16 | L4 “M=2000+fdr<0.01”验收口径未决 | 验收标准不明确 | PROGRESS L4 备注 | P2 |
| I17 | D1 旧结论作废，但旧报告/旧缓存可能仍在 | 用户可能引用旧排名 | D1 决策 + v1 数据 | P1（沟通） |
| I18 | LMNA L5 前端 Bootstrap 仍走 CDN（D9） | 内网离线环境可能样式缺失 | `frontend/index.html` 第 7 行 | P2 |
| I19 | LMNA 前端 `API_BASE` 硬编码 IP | 换 IP/域名需改代码；跨端口依赖 CORS | 实测 `index.html` | P1 |
| I20 | ProcessPool 子进程继承监听 socket，停止脚本只杀父进程 | 可能出现端口残留/僵尸监听 | 代码 + 脚本 + 实测 | P1 |
| I21 | 启停脚本只检查 PID，不检查端口占用 | 端口被占时新进程启动失败但脚本可能报成功 | 脚本内容 | P1 |
| I22 | 没有日志轮转 | 日志长期增长，可能占满磁盘 | 脚本/目录 | P2 |
| I23 | 没有健康检查、监控、告警 | 故障只能靠用户发现 | 现状 | P1 |
| I24 | 三个仓库都没有 CI | 回归/构建失败可能漏到部署 | 无 `.github` | P1 |
| I25 | 没有数据 checksum/manifest | 无法发现静默损坏/版本漂移 | 现状 | P1 |
| I26 | Easy_R 新实例数据是副本，不自动同步 | 用户/历史分裂 | 部署报告 + 实测 | P2 |
| I27 | 报告文件不过期、不清理 | 患者数据长期留存，磁盘增长 | 代码 | P2 |
| I28 | cmap/LMNA 无认证、无限流 | 内网任何人可跑全库扫描/导出 | 代码 | P1 |
| I29 | cmap 仓库含 10.4MB PDF 与图片 | 仓库体积大，克隆慢 | `ls` | P3 |
| I30 | `~/cmap_v2_data` 是软链农场 | 备份/迁移容易漏掉实体大文件 | 实测 `ls -la` | P1 |
| I31 | 旧 Easy_R `auth_secret.txt` 0664 | 同组用户可读 | 实测权限 | P2 |
| I32 | 没有备份/容灾方案 | 磁盘/误删会导致数据/缓存丢失 | 现状 | P1 |
| I33 | `fdr_reversal` 在 cmap 与 LMNA 方向相反 | 跨系统比较排名容易出错 | 代码 | P1（认知） |
| I34 | `restart_all.sh` 以“端口有响应”判活 | 可能把错误进程当成服务 | 脚本 | P2 |
| I35 | `deploy/nginx.conf` 仍是旧 IP `10.71.219.177` | 若直接套用会反代到错误地址 | 仓库文件 | P2 |
| I36 | 线上没有 `drug_median_lm.npy` | C3 即使部署也需先构建矩阵 | 实测 find | P1 |
| I37 | LMNA `config.py` 默认 `API_PORT=8001`，线上用 8004 覆盖 | 直接 `python main.py` 会起错端口 | 代码 + 启动脚本 | P2 |
| I38 | cmap `config.py` 默认 `API_PORT=8000`，线上用 8007 覆盖 | 直接 `run.py` 可能与邻居 8000 冲突 | 代码 + 启动脚本 | P2 |
| I39 | Easy_R 线上 CORS 为 8092，D2 目标为同源留空 | 部署形态与决策不一致 | 运行环境 | P2 |
| I40 | 前端 dist 硬编码 `http://10.39.15.238:8008/api` | 换 IP/域名需重新构建 | 实测 bundle | P2 |

---

## 11. 距离“成熟可靠”的差距与改进建议

先定义“成熟可靠”的最低标准：

1. 单一入口、统一 HTTPS、统一认证；
2. 进程可自启动、可幂等启停、可观测；
3. 有 CI、有回归测试、有发布流程；
4. 数据有 manifest、有校验、有备份；
5. 统计口径有文档、有决策、有版本；
6. 故障可发现、可定位、可回滚；
7. 多租户边界清晰。

以下按主题给出“现状 → 目标 → 建议 → 工作量/优先级”。工作量是粗略人日，仅用于排序。

### 11.1 统一入口与 HTTPS

| 现状 | 目标 | 建议 | 工作量 | 优先级 |
|---|---|---|---|---|
| 每个实例直接暴露端口；无 nginx；自签证书各自为政 | 一个域名/入口，统一 TLS，按路径反代到各服务 | 部署 nginx 或 Caddy；`/cmap/`、`/lmna/`、`/easyr/` 反代；统一证书；Easy_R 也走 HTTPS | 2–3 人日 | P1 |
| D2 的“同源 `/api`”未实现 | 前端与 API 同源，CORS 留空 | nginx 同源反代；重新构建 Easy_R/LMNA 前端；清空 CORS | 含在上项 | P1 |
| 自签证书浏览器警告 | 内部 CA 或受信证书 | 用内部 CA 签发域名证书；分发根证书；或 Caddy 自动 TLS | 1 人日 | P2 |

落地顺序建议：

1. 先选一个入口域名（如 `bio.xxx.internal`）；
2. nginx 配置 `client_max_body_size 50m`；
3. 先反代只读/低风险服务，再切 Easy_R；
4. 切换时保留旧端口一段时间，便于回滚；
5. 更新门户链接。

### 11.2 进程与自启动

| 现状 | 目标 | 建议 | 工作量 | 优先级 |
|---|---|---|---|---|
| 新实例不在 systemd/门户 | 开机自启、统一管理 | 为 cmap_v2/LMNA_v2/Easy_R_next 各写 systemd unit，或纳入 `portal-stack.service` | 1 人日 | P1 |
| 启停只查 PID，不查端口 | 幂等、可重入 | PID 文件 + 端口占用检查 + 进程组 kill；启动前 `ss` 校验 | 0.5–1 人日 | P1 |
| ProcessPool 子进程继承 socket | 停服务无残留 | `stop` 用进程组/`pkill -P`；systemd `KillMode=control-group` | 0.5 人日 | P1 |
| 单 worker 无故障隔离 | 崩溃自动拉起 | systemd `Restart=always`；健康检查 | 含上项 | P1 |
| 无日志轮转 | 日志可控 | systemd `StandardOutput` + journald，或 logrotate | 0.5 人日 | P2 |

### 11.3 监控、日志与告警

| 现状 | 目标 | 建议 | 工作量 | 优先级 |
|---|---|---|---|---|
| 无监控 | 关键指标可见 | 至少：端口存活、`/health`、CPU/内存/磁盘、任务队列长度、请求耗时 | 1–2 人日 | P1 |
| 无告警 | 故障主动通知 | 简单脚本 + 邮件/企业微信；或 Prometheus + Alertmanager | 1 人日 | P2 |
| 日志分散 | 统一检索 | journald 或集中日志；保留 7–30 天 | 1 人日 | P2 |
| 无审计 | 关键操作可追溯 | 记录 compute/delete/export/登录；不记录敏感内容 | 1–2 人日 | P2 |

最小可用监控清单：

```text
- TCP 端口存活：8001/8003/8004/8005/8006/8007/8008/8081/8083/8084/8090/8091/8092/8888
- HTTP /health：cmap 8007/8001、LMNA 8004/8003、Easy_R 8008/8006/8005
- 磁盘：/home 使用率
- 进程：PID 文件与实际进程一致
- 任务：LMNA tasks pending/running 数量、cmap tau_job 数量
- 日志：ERROR/Exception 关键字
```

### 11.4 CI 与测试

| 现状 | 目标 | 建议 | 工作量 | 优先级 |
|---|---|---|---|---|
| 无 CI | PR 必须过测试 | GitHub Actions：三仓库各自 pytest；Easy_R 加 vitest + build；cmap/LMNA 加前端静态检查 | 1–2 人日 | P1 |
| 无覆盖率 | 防止倒退 | `pytest-cov` + 低阈值；核心统计函数单独要求 | 1 人日 | P2 |
| 测试依赖夹具 | 关键路径更真实 | 增加小规模真实矩阵切片测试；保留夹具快速测试 | 2 人日 | P2 |
| 无发布流程 | 可重复部署 | 打 tag、生成 release notes、部署脚本校验版本 | 1 人日 | P1 |

CI 建议矩阵：

| 仓库 | 后端 | 前端 | 其他 |
|---|---|---|---|
| LMNA | `pytest -q` | 静态 HTML 无构建 | L8 数据切片测试 |
| cmap | `pytest -q` | 无构建（单文件） | C3 小矩阵 null 测试 |
| Easy_R | `pytest -q` | `npm test -- --run` + `npm run build` | 报告安全测试 |

### 11.5 数据校验与快照

| 现状 | 目标 | 建议 | 工作量 | 优先级 |
|---|---|---|---|---|
| 无 manifest | 数据可追溯 | `data_manifest.json`：path/size/md5/mtime/source/command | 1 人日 | P1 |
| 启动不自检 | 错误早发现 | 启动校验 shape、CSV 行数、首/中/末 ID 抽样、GCTX 存在 | 0.5 人日 | P1 |
| 无备份 | 可恢复 | 备份 CSV/manifest/缓存元数据；23GB 矩阵至少做校验和与异地副本 | 2–3 人日 | P1 |
| 软链农场易漏 | 迁移完整 | 用 `rsync -L` 或 manifest 明确实体/链接；文档标注 | 0.5 人日 | P1 |
| 缓存无清单 | 可清理 | 生成缓存索引（文件、大小、参数哈希、生成时间） | 1 人日 | P2 |

启动自检建议（伪代码）：

```python
assert fast_matrix_size == 12328 * 473647 * 4
assert len(col_ids) == 473647
assert len(row_ids) == 12328
assert col_ids[0] == gctx_col_ids[0]
assert col_ids[-1] == gctx_col_ids[-1]
assert row_ids[0] == gctx_row_ids[0]
assert row_ids[-1] == gctx_row_ids[-1]
```

### 11.6 统一认证与权限

| 现状 | 目标 | 建议 | 工作量 | 优先级 |
|---|---|---|---|---|
| cmap/LMNA 无登录 | 统一登录/权限 | 在 nginx 层做 Basic/OIDC，或应用层加 token；至少区分只读/计算/管理 | 2–3 人日 | P1 |
| Easy_R 自建账号 | 可保留或接入统一 | 短期保留；长期接入 OIDC/LDAP | 3–5 人日 | P2 |
| 删除接口单一 token | 角色权限 | 管理员角色 + 审计 | 1 人日 | P2 |
| 无速率限制 | 防滥用 | nginx `limit_req` 或应用层令牌桶 | 0.5 人日 | P1 |

### 11.7 统计口径与产品化

| 现状 | 目标 | 建议 | 工作量 | 优先级 |
|---|---|---|---|---|
| C3 p/FDR 在生产规模不可显著 | 可解释的显著性 | N3：调大 M、限制 BH 家族、或改用经验 FDR；在 UI 明示局限 | 2–3 人日 | P1 |
| LMNA `fdr_reversal≈0.99` | 同上 | 统一药物级 null 策略；在 UI 明示分辨率 | 2 人日 | P1 |
| D1 旧结论作废 | 用户知晓 | 发布说明 + UI 提示 + 旧报告标注 | 0.5 人日 | P1 |
| D4 注释缺失 | 判档完整 | 下载/构建 `gene_annotations.tsv`；来源与许可确认 | 1–2 人日 | P2 |
| L4 验收口径未决 | 可验收 | 明确 M 与阈值；写进测试 | 0.5 人日 | P2 |
| D7 默认值矛盾 | 行为一致 | 确认默认 150 还是 500；更新代码/文档 | 0.2 人日 | P2 |
| 符号约定易混 | 不误用 | UI 上明确“高分=逆转”/“负分=逆转”；文档固定 | 0.5 人日 | P1 |

### 11.8 功能补齐与统一系统

| 现状 | 目标 | 建议 | 工作量 | 优先级 |
|---|---|---|---|---|
| v1 有 l4zsvc/FDA/Figure3/export，v2 没有 | 功能不丢失 | N7：逐项移植或明确下线；先移植导出，再评估 FDA/Figure3 | 5–10 人日 | P1 |
| 两个 LMNA 并存 | 单一权威实例 | 完成移植后下线 v1，或把 v1 标为“历史只读” | 1 人日 | P1 |
| 三个 Easy_R 并存 | 单一权威实例 | 迁移数据后下线旧实例；保留回滚窗口 | 1–2 人日 | P2 |
| 三个系统各自登录/入口 | 统一门户 | D10 P3 统一系统；先做统一导航与 SSO | 10+ 人日 | P3 |
| 新实例不在门户 | 用户能找到 | 更新 `~/portal/index.html`，加“新版”标记 | 0.2 人日 | P1 |

---

## 12. 人工决策清单

### 12.1 既有 D1–D10

「据 PROGRESS.md」

| 决策 | 内容 | 当前状态 | 交接建议 |
|---|---|---|---|
| D1 | KS 符号约定修改后旧结论作废，是否发公告 | ✅已决：默认 FDR 0.05 + KS 0.2；论文模式 0.001 可配；合并时写变更说明 | 执行层面仍需在 UI/发布说明中告知用户；旧 v1 结论标注作废 |
| D2 | Easy_R 生产端口与 CORS | ✅已决：nginx 同源反代 `/api`，CORS 留空，端口 8006/8091 | **实际未按此部署**：新实例 8008/8092、CORS=8092；需 N5/N10 重新对齐 |
| D3 | `MIN_SH_SAMPLES=422` 阈值是否过硬 | ✅已决：默认 3，样本不足 422（可配置） | 保持 |
| D4 | `gene_annotations.tsv` 是否上线 | ⬜待定 | 建议上线；先确认来源/许可；见 N4 |
| D5 | Touchstone 用 GSE92742 还是 LINCS2020 | ⬜待定 | 与 C5/Tau 方案绑定；先确认数据位置与许可 |
| D6 | gunicorn `-w 1 --threads 8` | ✅已决 | 新实例已按此部署；旧实例仍是 `-w 4`，需 N9 |
| D7 | CSV topN 500→150 | ✅已决：做成可配置（默认500，可改150） | **与代码默认 150 矛盾**；需确认并统一（N8） |
| D8 | 每次刷新重新登录 | ✅已决：保留 | 保持 |
| D9 | CDN 字体/库离线化范围 | ⬜待定 | LMNA L5 仍用 Bootstrap CDN；cmap C4 已本地化；建议统一离线化 |
| D10 | P3 统一系统是否启动 | ⬜待定 | 先完成 P0/P1 治理，再启动统一系统 |

### 12.2 本次新增决策 N1–N12

#### N1：是否立即把 C3 部署到 cmap_v2

- 背景：GitHub master 已合并 C3（`40dfe9c`），线上 8007 仍是 `0a02aa3`，没有 p/FDR/null_z。
- 选项：
  - A. 立即部署 C3 + 构建药物中位数矩阵；
  - B. 先只部署 C3 代码，矩阵随后构建；
  - C. 暂不部署，等 N3 的 FDR 方案确定。
- 建议：**A**。C3 的字段和降级逻辑已经测试；矩阵构建可复用 LMNA 缓存，成本可控。若不先部署，用户会持续看到“没有 FDR”。
- 影响：8007 需要短暂重启；需确认 `CMAP_DATA_DIR` 下有 `drug_median_lm.npy`；旧 8001 不受影响。
- 验收：`TauSearchResult` 返回 `p_value/fdr/null_z`；`null_calibration=ok`；小规模抽样与交付文档一致。

#### N2：是否部署 L5 前端并改为同源

- 背景：线上 LMNA 前端是 L5 之前版本，缺少适用性卡片、FDR 列、fast 警告、XSS 转义。
- 选项：
  - A. 部署 L5 前端，保留 `API_BASE=https://10.39.15.238:8004`（跨端口，CORS 已配）；
  - B. 部署 L5 前端并改为 `API_BASE=''` + FastAPI 同源 mount；
  - C. 暂不部署。
- 建议：**B**。L5 的设计目标就是同源；同源可去掉 CORS，减少证书/跨端口问题。若时间紧，先 A 再 B。
- 影响：需要确认 `main.py` 的 StaticFiles mount 与 API 路由顺序；前端换版后用户会看到新 UI。
- 验收：8084 页面加载无 CORS 错误；`/api/genes/TP53/suitability` 在页面展示；FDR 列出现。

#### N3：药物级 null / FDR 的生产口径

- 背景：
  - LMNA `DRUG_NULL_N=10000`，`fdr_reversal≈0.99`；
  - cmap C3 生产家族约 19,811，FDR 下限≈1.98；
  - 默认 M 下 p/FDR 只能做相对排序，不能做“显著/不显著”的硬判据。
- 选项：
  - A. 提高 M 到 `~2e6`（计算/内存成本大幅上升）；
  - B. 限制 BH 家族（如只对 top-K 或预筛药物校正），并在 UI 说明；
  - C. 改用经验 FDR/置换分布的其他校准；
  - D. 保留现状，UI 明确“仅相对排序”。
- 建议：**B + D 组合**：短期在 UI 明示局限；中期对 top-K 做受限 BH，并给出方法说明。A 作为离线验证，不作为在线默认。
- 影响：统计口径变化会影响排名/显著性文案；需要发布说明和测试更新。
- 验收：文档、UI、测试三处口径一致；有基准数据对比。

#### N4：D4 注释表是否上线

- 背景：`gene_annotations.tsv` 不存在，适用性第一层显示“未知”；TP53 因此为 yellow。
- 选项：
  - A. 使用 Repurposing Hub / GO / 人工整理的数据构建；
  - B. 只上线“表达/组织特异性”最小字段；
  - C. 维持“未知”，不改判档。
- 建议：**A**，但先确认数据许可与字段映射；若许可不清，先 B。
- 影响：判档结果变化；需要重新计算签名或至少刷新 qc 缓存；用户需要发布说明。
- 验收：`GENE_ANNOTATIONS_PATH` 可读；`/suitability` 返回注释字段；TP53 等样本基因档位有解释。

#### N5：Easy_R 是否上 HTTPS

- 背景：8005/8006/8008 与 8090/8091/8092 全部明文 HTTP；登录 token 与患者数据在内网明文传输。
- 选项：
  - A. 在 nginx/Caddy 统一 TLS 终止（推荐）；
  - B. 每个 uvicorn 直接加自签证书；
  - C. 维持 HTTP（仅限完全可信内网）。
- 建议：**A**，与 N10 统一入口一起做；若短期做不到，至少给 8008 加自签 HTTPS。
- 影响：前端 `VITE_API_BASE_URL` 改为 `https://.../api` 或同源 `/api`；需要重建 dist；CORS 可清空。
- 验收：浏览器 HTTPS 访问；登录/报告下载正常；无混合内容。

#### N6：新实例是否加入门户与自启动

- 背景：新实例不在 `portal/index.html`，也不在 `portal-stack.service`/`restart_all.sh`；重启服务器后需手工拉起。
- 选项：
  - A. 加入 `restart_all.sh` + systemd；
  - B. 单独写 `new-stack.service`，与旧 stack 分离；
  - C. 维持手工。
- 建议：**B**。单独 unit 可以避免影响旧服务，也便于逐步切换。
- 影响：需要写 unit、PID/日志、健康检查、启动顺序；门户加“新版”链接。
- 验收：重启服务器后新实例自动恢复；`systemctl status` 正常；门户可点。

#### N7：l4zsvc/FDA/Figure3/export 是否移植

- 背景：v2 缺 v1 的多个功能；直接下线 v1 会丢失能力。
- 选项：
  - A. 全量移植；
  - B. 只移植导出（最常用），FDA/Figure3 标记“历史功能”；
  - C. 保留 v1 作为只读历史实例，不再维护。
- 建议：**B**，先移植导出；FDA/Figure3 做用户调研后再决定；v1 暂时保留。
- 影响：移植涉及前端按钮、后端路由、缓存/导出格式；需要单独任务与测试。
- 验收：导出 CSV/zip 与 v1 对齐；用户可在 v2 完成主要工作流。

#### N8：D7 默认 topN 到底是多少

- 背景：PROGRESS 写“默认500，可改150”，但 `app/config.py` 实际默认 150。
- 选项：
  - A. 默认 150（与代码一致，符合 C1 标题“150修复”）；
  - B. 默认 500（与决策文字一致）；
  - C. 不设默认，强制用户选择。
- 建议：**A**，并更新 PROGRESS 文字。C1 的目标就是限制到 150，代码是事实。
- 影响：CSV 导出条数；需在 UI/文档说明可配置。
- 验收：PROGRESS、README、代码、UI 四处一致。

#### N9：旧 cmap 实例如何处理

- 背景：旧 8001 使用旧 CSV（未修）、旧代码（无 C1/C2/C3）、`-w 4`；存在错误结果风险。
- 选项：
  - A. 升级旧实例到 master 并修 CSV；
  - B. 保留旧实例但明确标注“历史/不保证正确”，引导用户到 8007；
  - C. 直接下线旧实例。
- 建议：**B 短期 + A 中期**。不要在没有验证的情况下直接替换旧 CSV；先让用户迁移到 8007，再找窗口升级/下线。
- 影响：旧用户书签、门户链接、历史结果；需要沟通。
- 验收：8007 功能覆盖旧实例；旧实例有醒目提示；最终下线。

#### N10：是否启动统一入口/统一认证

- 背景：无 nginx、无统一登录、CORS 被动开放、证书各自为政。
- 选项：
  - A. nginx/Caddy + 统一 TLS + 路径反代；
  - B. 仅统一 TLS，不做认证；
  - C. 维持现状。
- 建议：**A**，分阶段：先 TLS/反代，再统一认证（OIDC/LDAP 或 nginx auth）。
- 影响：所有 URL 变化；需要更新门户、前端构建、CORS、文档；回滚方案必须准备。
- 验收：单一入口可访问三系统；HTTPS 无警告（内部 CA）；认证可开关；旧端口保留回滚。

#### N11：是否建立数据 manifest/启动自检

- 背景：23GB 矩阵、CSV、缓存都没有校验和；L8 的教训是“顺序错了但服务不报错”。
- 选项：
  - A. 只做 manifest（离线）；
  - B. manifest + 启动轻量自检；
  - C. 完整校验和 + 定期校验。
- 建议：**B**，逐步到 C。
- 影响：启动多几秒；需要维护 manifest；数据更新流程要同步更新 manifest。
- 验收：启动时能发现 CSV 行数/首末 ID 不符；manifest 与文件一致。

#### N12：是否建立 CI 与发布流程

- 背景：三仓库无 CI；合并后靠人工跑测试；部署版本与 GitHub HEAD 已出现两次偏差。
- 选项：
  - A. GitHub Actions 跑 pytest/build；
  - B. 仅本地 pre-push hook；
  - C. 维持现状。
- 建议：**A**；至少覆盖后端测试与 Easy_R 前端 build；再加一个“部署版本核对”脚本。
- 影响：需要 GitHub Actions 额度/网络；测试环境准备；合并门禁。
- 验收：PR 自动跑测试；失败不能合并；部署前打印 commit hash。

#### N13：备份与容灾

- 背景：没有备份策略；`~/cmap_v2_data` 是软链农场；缓存重建耗时。
- 选项：
  - A. 只备份 CSV/manifest/配置；
  - B. A + 定期备份缓存元数据；
  - C. 全量备份（含 23GB 矩阵）。
- 建议：**B**；23GB 矩阵至少有校验和与一份异地副本（离线）。
- 影响：磁盘/网络成本；恢复演练。
- 验收：能从备份恢复 CSV 与缓存；恢复后有验收脚本。

#### N14：监控与告警

- 背景：无监控；故障靠用户发现。
- 选项：
  - A. 简单脚本 + 邮件；
  - B. Prometheus + Grafana + Alertmanager；
  - C. 云监控。
- 建议：**A** 起步，稳定后 B。
- 影响：需要维护监控服务；告警阈值。
- 验收：端口/健康/磁盘/任务异常能在 5 分钟内通知。

### 12.3 建议决策顺序

第一批（P0/P1，先做）：

1. N9：明确旧 cmap 的处置，避免用户继续使用可能错误的旧实例；
2. N1：部署 C3（至少让 8007 有 p/FDR 字段）；
3. N2：部署 L5 前端（让用户看到适用性/FDR）；
4. N6：新实例进 systemd/门户（避免重启后失联）；
5. N11：数据 manifest + 启动自检（防止 L8 类问题复发）；
6. N12：CI（防止回归）。

第二批（P1）：

7. N3：确定 null/FDR 生产口径；
8. N5 + N10：HTTPS/统一入口（可合并实施）；
9. N7：导出功能移植；
10. N13/N14：备份与监控。

第三批（P2/P3）：

11. N4：注释表；
12. N8：D7 文案统一；
13. D5/D9/D10：Touchstone、离线化、统一系统。

---

## 附录 A：只读核对命令速查

以下命令全部只读，可在交接/排障时使用。不要执行其中的写操作（已标注）。

### A.1 连接与环境

```bash
ssh -i ~/.ssh/lmna_deploy keji@10.39.15.238

# 非交互 ssh 没有 conda PATH，需要先初始化
source ~/miniconda3/etc/profile.d/conda.sh
conda activate cmap      # 或 easyr
```

### A.2 端口与进程

```bash
# 监听端口
ss -ltnp

# 本项目相关进程
ps -eo pid,ppid,lstart,cmd | grep -E 'cmap|lmna|Easy_R|gunicorn|uvicorn|serve|http.server' | grep -v grep

# 查看某个 PID 的工作目录与命令行
readlink /proc/<pid>/cwd
tr '\0' ' ' < /proc/<pid>/cmdline; echo

# 查看父子关系（确认是否进程池 worker）
ps -o pid,ppid,lstart,cmd -p <pid>,<child1>,<child2>
```

### A.3 健康检查

```bash
curl -k -s -o /dev/null -w '%{http_code} %{time_total}s\n' https://127.0.0.1:8007/health
curl -k -s -o /dev/null -w '%{http_code} %{time_total}s\n' https://127.0.0.1:8004/api/health
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' http://127.0.0.1:8008/api/health
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' http://127.0.0.1:8888/
curl -k -s -o /dev/null -w '%{http_code} %{time_total}s\n' https://127.0.0.1:8001/health
```

### A.4 版本与部署核对

```bash
# 仓库
cd ~/lmna_v2 && git log -1 --oneline        # 若不是 git 仓库，说明是拷贝部署
cd ~/cmap_v2 && git log -1 --oneline
cd ~/Easy_R_v2_next && git log -1 --oneline

# 文件时间
stat -c '%y %s %n' ~/cmap_v2/app/config.py ~/lmna_v2/backend/main.py ~/Easy_R_v2_next/backend/app/main.py

# 运行环境（只打印非敏感项）
tr '\0' '\n' < /proc/<lmna-pid>/environ | grep -E '^(DATA_PROVIDER|BOOTSTRAP_N|FDR_THRESHOLD|DRUG_NULL_N|CMAP_DATA_DIR|LMNA_CACHE_DIR)='
```

### A.5 数据与缓存

```bash
# 数据目录
ls -la ~/cmap_v2_data
du -sh ~/cmap/cmap_data ~/cmap_v2_data ~/lmna_v2_cache

# 矩阵与 CSV
stat -c '%s %n' ~/cmap/cmap_data/fast_matrix.npy
md5sum ~/cmap_v2_data/col_sig_ids.csv ~/cmap_v2_data/row_gene_ids.csv

# 缓存
ls -lh ~/lmna_v2_cache
cat ~/lmna_v2_cache/_shrna_rank_matrix.v2.154993.shape.txt

# GCTX 元数据（需要 h5py）
source ~/miniconda3/etc/profile.d/conda.sh
conda activate cmap
python - <<'PY'
import h5py
p = "/home/keji/cmap/cmap_data/GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx"
with h5py.File(p, "r") as f:
    print(f["0/META/COL/id"][:3])
    print(f["0/META/ROW/id"][:3])
    print(f["0/DATA/0/matrix"].shape)
PY
```

### A.6 证书

```bash
for f in ~/cmap/certs/cmap.crt ~/cmap_v2/certs/cmap.crt \
         ~/lmna_app/LMNA/backend/lmna.crt ~/lmna_v2/backend/lmna.crt; do
  echo "-- $f"
  openssl x509 -in "$f" -noout -subject -dates
done

# 私钥权限（不要 cat）
ls -l ~/cmap_v2/certs/cmap.key ~/lmna_v2/backend/lmna.key
```

### A.7 门户与自启动

```bash
cat ~/portal/index.html | grep -n 'href='
systemctl is-enabled portal-stack.service
systemctl is-active portal-stack.service
systemctl cat portal-stack.service
cat ~/portal/restart_all.sh
```

### A.8 日志

```bash
tail -50 ~/cmap_v2/cmap_v2.log
tail -50 ~/lmna_v2/server_v2.log
tail -50 ~/lmna_v2/frontend_v2.log
tail -50 ~/Easy_R_v2_next/backend_v2.log
tail -50 ~/Easy_R_v2_next/frontend_v2.log
```

### A.9 不要执行的命令

以下命令会修改生产状态，非部署窗口不要执行：

```bash
# 不要随手杀进程
pkill -f uvicorn
pkill -f python3
kill -9 <pid>

# 不要删除/重建缓存
rm -rf ~/lmna_v2_cache
rm -f ~/lmna_v2_cache/_shrna_rank_matrix.*

# 不要替换共享 CSV
cp ... ~/cmap/cmap_data/col_sig_ids.csv

# 不要重启/修改 systemd
systemctl restart portal-stack.service
```

---

## 文档结束

本文基于 2026-10-18 的代码、部署报告与服务器只读实测编写。若发现事实变化，请按 0.3 节的维护约定更新，并在 `deliveries/docs-system-handoff.md` 中记录差异。

关键提醒（再次强调）：

1. **GitHub 合并 ≠ 线上部署**：cmap C3、LMNA L5 前端都尚未上线；
2. **8003/8004 的多 PID 是进程池 worker**，不是重复服务；
3. **cmap 与 LMNA 的 `fdr_reversal` 方向相反**，跨系统比较前先确认符号；
4. **旧 cmap 仍使用旧 CSV**，结果正确性没有保证；
5. **多租户服务器上任何写操作都要先确认影响面**。




# task-L7 交付说明（设计文档）

任务ID / 分支：task-L7 / `docs/L7-proposals`（基线 `origin/main` @ `315f965`）

交付文档：

- `docs/design/L7a-shared-data-layer.md` — 共享 L1000 landmark memmap 数据层
- `docs/design/L7b-instance-xsum.md` — 实例级 XSUM（先实例、后药物中位数）
- `docs/design/L7c-launched-drugs.md` — 仅已上市药物开关（Repurposing Hub `Launched`）
- `docs/design/L7d-signature-sources.md` — trt_oe / trt_xpr / 用户上传差异基因
- `docs/design/L7e-l3-provider.md` — L3Provider 与同板对照 robust z
- `docs/design/L7f-task-system.md` — SQLite 任务表 + 独立 worker

每份文档均包含：现状与代码/数据证据、接口/数据格式、迁移步骤、性能/容量估算、验收清单、风险、工作量、待人工确认项。

## 关键结论与推荐

1. **L7a（共享数据层）**：生成 `(473647, 978)` float32、1.85 GB 的签名优先 memmap；只读 978 行，不扫 23 GB。服务器实测 gather 4.88 s + 转置 1.09 s + 落盘 0.39 s。当前 `get_expression_matrix` 读 5000 列 6.36–6.63 s，整库外推 10.0–10.5 min/遍；新层同块 0.02 s。推荐先实施，作为 L7b 的基础。注意 cmap 的 `/extract` 需要 12328 维，不能直接切到 landmark 层，需保留旧路径或另建 23.36 GB 全基因层。
2. **L7b（实例级 XSUM）**：只需 802 MB 实例矩阵与 0.82 MB 分数向量；单次查询约 1–3 s。与现有“先中位数”口径全库 Spearman 0.985–0.997、Top-100 重合 100/100，但中段排名位移可达 6,877 位。预实验的 29 对已知抑制剂在两种口径下都没有进前 100/500；必须用 L3 报告 4.4b 的 394 靶点/LOHO 夹具复跑后才能决定是否切默认，并需重跑 L4 的 FDR 校准。
3. **L7c（仅已上市药物）**：Repurposing Hub 2020-03-24 中 `Launched` 2,427 个，但与 GSE92742 匹配后只有 1,222 个唯一 LINCS 名称 / 36,573 个实例（17.8%）。建议 BRD 基础 ID + 规范化名称 + 别名表；26 个盐型词要谨慎（酯类不可剥离）。**许可证是硬约束**：文件头明确“non-commercial use only”，与部分二手资料的 CC BY 4.0 说法冲突，需 D4 结论；建议派生映射在部署时生成、不入公开仓库。
4. **L7d（备选来源）**：trt_oe 已在现有矩阵（22,205 实例 / 3,114 基因 / 10 细胞系），优先做；用户上传成本最低、产品价值最高（3–4 人日）；trt_xpr 在 GSE70138 只有 3,882 签名 / 53 个基因 / 11 细胞系，L5 文件 5.37 GB，最后做。与 L3 的衔接只新增 `source/provenance/concordance` 字段，不改现有判档规则。
5. **L7e（L3Provider）**：GSE92742 Level3 为 1,319,138×12,328、52.4 GB，服务器目前没有。关键修正：shRNA 的同板对照是 `ctl_vector`（空载体），1,467 块 shRNA 板全部有同板 `ctl_vector`；`ctl_vehicle` 同板仅 2,323 个实例/172 块板，按它做只能覆盖 613/448,737 个 shRNA 实例。建议先做 2 人日 spike，不建议直接全量实施；数值无法与论文 Table S1 完全对齐。
6. **L7f（任务系统）**：SQLite `jobs` 表 + 独立 worker + 心跳/重试/取消/幂等；`all_scores` 移出 JSON 到 `.npz`。HTTP 契约不变，`JobStore` 抽象为后续 Redis/Postgres 留口。工作量约 5 人日。

## 验收逐条结果

- [x] 6 份文档齐全，均在 `docs/design/`，均包含接口、数据格式、迁移步骤、工作量估算。
- [x] 代码行号按基线 `315f965` 核对；不符处按函数名定位（`l5_provider.get_expression_matrix`、`drug_median_cache._ensure_drug_median_cache`、`drug_scorer._xsum_score`、`l3_provider.__init__`、`task_queue.submit`）。
- [x] 只新增 `docs/design/` 与 `deliveries/`，未修改任何业务代码、配置、前端或测试。
- [x] 服务器只读：仅读取 `~/cmap/cmap_data`、`~/LMNA/cache`、`inst_info`/元数据；未改生产目录、未装依赖、未重启服务。基准测试在服务器 `/tmp` 写了一个临时 `.npy` 并在测试后删除，未触碰生产目录。
- [x] 网络：git/curl 均通过 `127.0.0.1:7897` 代理；未直连 GitHub。
- [x] 未推 `main`/`master`；只推 `docs/L7-proposals`。
- [x] PROGRESS 看板 L7 行已按流程更新为进行中，并在推送后改为待合并 + commit hash。
- [x] 交付说明使用任务模板，包含分支、文档清单、关键结论、待确认项、发现但未处理项。

## 待人工确认（🧑‍⚖️）

1. **D4 / L7c 许可**：Repurposing Hub 文件头写“non-commercial use only”，与 CC BY 4.0 的二手说法冲突。是否允许在公开仓库提交派生的 `launched` 映射？建议不允许，改为部署时本地生成。
2. **L7a 共享层位置与 cmap 语义**：共享目录最终放哪？cmap 是否接受“WTCS 仅 landmark 查询走快路径、混合查询回退”？
3. **L7b 默认口径**：是否在夹具证明增益后把 `instance_first` 设为默认？切换后是否同步重跑 L4 的 null/FDR？
4. **L7c 默认范围**：是否保持 `all` 为默认、`launched` 仅作为开关？`Launched` 用 2020-03-24 固定版还是升级到 2025-08-19？
5. **L7d 上传与 xpr**：用户上传是否对匿名用户开放？trt_xpr 用 GSE70138（53 个基因）还是等 LINCS2020？
6. **L7e 对照语义**：确认 shRNA 同板对照用 `ctl_vector` 而非 `ctl_vehicle`；是否值得投入 9–13 人日做 L3？是否批准 52.4 GB 下载与独立 venv/容器解析？
7. **L7f 技术选型**：第一阶段 SQLite 还是直接 Postgres？worker 并发数、结果保留期、是否允许短暂停机迁移？

## 发现但未处理

1. **L7b 预实验没有找回率增益**：29 对高置信抑制剂在两种 XSUM 口径下均未进前 100/500，细胞系匹配后的最佳百分位约 0.285。原因可能是 L5 MODZ、签名未做 LOHO 稳定性筛选、细胞系混合或 L1 符号约定；正式结论必须等 L0/L1/L3 夹具，不应据此判断实例级口径无效。
2. **L7e 的任务描述与数据不一致**：任务原文说“同板 vehicle”，但 `ctl_vehicle` 与 shRNA 同板极少；实际可用的是 `ctl_vector`。已在文档中标注，需人工确认后再实施。
3. **L7c 覆盖缺口**：约一半已上市药物在 GSE92742 中没有 profile；换 GSE70138/LINCS2020 才能改善，但会引入版本/许可问题。
4. **L7a 与 cmap `/extract` 的冲突**：landmark 层不能服务 12328 维返回；需要保留旧路径或增加 23.36 GB 全基因层，成本已列在文档中。
5. **服务器只有 Level5**：L3/L4 数据需要新下载（52.4/53.3 GB），当前服务器未安装 cmapPy/h5py 的生产依赖；数据准备需单独审批。
6. **`all_scores` 体积**：当前每个药物结果 JSON 含 19,811 项；L7f 建议移到 NPZ，但在 L7f 实施前仍会膨胀缓存，未在本次修改。

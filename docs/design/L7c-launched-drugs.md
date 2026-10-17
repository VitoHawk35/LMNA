# L7c · 仅 FDA 已上市药物开关（Repurposing Hub `Launched`）（设计文档）

- 状态：方案待人工确认（只出文档，未实施）
- 基线：LMNA `main` @ `315f965`
- 关联：L3（第一层注释已使用 Repurposing Hub，D4 同源）、L4（药物级 null/FDR 的分母会变化）、L7a（药物中位数矩阵需按范围重建）

## 1. 结论摘要

目标：让用户可以选择“只对已上市药物排序”（论文口径 >600 种），默认仍为全部 `trt_cp`（19,811 种），通过开关切换。

Repurposing Hub 2020-03-24 版：

- 药物注释 6,798 行，`clinical_phase == "Launched"` **2,427** 行（唯一名称 2,427）；
- 与 GSE92742 的 `trt_cp` 做匹配后，实际能覆盖的 LINCS 药物为 **1,222 个唯一 `pert_iname` / 36,573 个实例（17.8%）**；
- 匹配路径：BRD 基础 ID 命中 968 个药物（25,509 实例）；规范化名称命中 1,177 个；两者并集 1,221 个；InChIKey 交集 832 个。名称匹配是必要的兜底，单靠 ID 会漏 254 个。
- 因此“仅 FDA 已上市”在 LMNA 里实际是“~1,222 种在 GSE92742 中有数据的已上市药物”，不是 2,427 种；界面必须显示真实候选数，不能写“FDA 批准 2,427 种”。

许可证是硬约束：下载文件的头部明确写 **“The Drug Repurposing Hub data is provided for non-commercial use only.”**，并含免责声明。部分二手来源称元数据为 CC BY 4.0，但与文件自带限制不一致。建议：

1. 不把 Hub 原始文件或派生的 `launched` 映射提交到公开 GitHub 仓库；
2. 在部署时由使用者自行下载并用脚本生成 `drug_scope_launched_v1.csv`，文件放在 `cache/` 或服务器数据目录（已被 `.gitignore` 忽略）；
3. 功能默认关闭；是否上线由 D4 的许可结论决定；
4. 如果许可不允许，退化方案是用 LINCS 自己的 `pert_info.is_touchstone == 1`（2,429 个化合物）作为“已上市/核心参考集”的近似，但它与 `Launched` 不等价，必须在 UI 明确标注。

## 2. 现状与证据

### 2.1 代码事实

- `backend/l5_provider.py:89-97`：`_drug_df = sig_info[pert_type == "trt_cp"]`，没有药物范围过滤；当前 19,811 个唯一 `pert_iname`。
- `backend/drug_median_cache.py:36-48`：按 `pert_iname` 分组，全部药物进入中位数矩阵；缓存文件 `_drug_median_matrix.npy` 74 MiB、`_drug_names.csv` 19,811 行。
- `backend/drug_scorer.py:62-69`：所有药物一起排序，返回 top/bottom；没有“已上市”标记。
- `backend/main.py:68-75`：`/api/genes` 只列基因；没有药物范围参数。
- L3 任务已把 Repurposing Hub 的 `moa` 用于第一层注释，并在任务文件中标注“仅限非商业用途，需确认许可”（D4）。

### 2.2 数据事实（只读核对）

GSE92742（`sig_info` + `pert_info`）：

| 项目 | 数值 |
|---|---|
| `trt_cp` 实例 | 205,034 |
| 唯一 `pert_iname` | 19,811 |
| 唯一 `pert_id` | 20,413 |
| `pert_info` 中 `trt_cp` 扰动剂 | 20,413 |
| `pert_info.is_touchstone == 1` 的 `trt_cp` 扰动剂 | 2,429 |
| 名称中含盐/水合物后缀（hydrochloride/mesylate/...）的唯一名称 | 25 |
| 名称大小写 | 绝大多数小写；存在 `KUC107191N` 等大写；空格用连字符替代（`trichostatin-a`） |

Repurposing Hub 2020-03-24（`repurposing_drugs_20200324.txt`，下载文件 530,302 B；skip 9 行注释后 6,798 行）：

| clinical_phase | 行数 |
|---|---|
| Launched | 2,427 |
| Preclinical | 2,310 |
| Phase 2 | 813 |
| Phase 1 | 566 |
| Phase 3 | 458 |
| Withdrawn | 95 |
| Phase 1/Phase 2 | 85 |
| Phase 2/Phase 3 | 44 |

- 列：`pert_iname, clinical_phase, moa, target, disease_area, indication`；**没有 `pert_id`**。
- 样本注释 `repurposing_samples_20200324.txt`（13,553 行）有 `broad_id`（如 `BRD-K76022557-003-28-9`）、`pert_iname`、`InChIKey`、`pubchem_cid`。基础 ID 为 `BRD-[A-Z]\d+`（如 `BRD-K76022557`），可与 LINCS `pert_id` 直接对齐。
- 2025-08-19 版本仍约 6,798 个化合物、2,427 个已上市；本方案建议固定 2020-03-24 以保证可复现，升级需重跑匹配与计数。

### 2.3 匹配覆盖率实测

对 2,427 个 `Launched` 药物与 GSE92742 的 19,811 个唯一 `trt_cp` 名称做匹配：

| 匹配方式 | 命中的 Hub 药物数 | 覆盖的 LINCS 实例数 |
|---|---|---|
| BRD 基础 ID（`BRD-[A-Z]\d+`） | 968 | 25,509（12.4%） |
| 规范化名称（大小写/空格/连字符/标点） | 1,177 | — |
| ID 或名称并集 | 1,221 | 36,573（17.8%） |
| InChIKey（通过 `pert_info`） | 832 | — |
| 并集后的唯一 LINCS 名称 | 1,222 | — |

结论：约一半的已上市药物在 GSE92742 中没有可用 profile（或名称无法对齐）。这既是数据覆盖问题，也是名称映射问题；需要别名表和人工抽检。

## 3. 目标与非目标

### 3.1 目标

- 增加可配置的药物范围：`all`（默认）/ `launched`。
- 提供可审计的匹配产物（每个 LINCS `pert_id` 对应哪个 Hub 药物、用什么方法匹配、置信度）。
- 药物范围变化时，药物中位数缓存、排序分母、L4 的 FDR 分母都可复现地重建。
- 失败可回滚，不影响默认的全部药物模式。

### 3.2 非目标

- 不把 Repurposing Hub 的 `moa/target/indication` 全部搬进 LMNA（L3 只用 `moa` 做注释）。
- 不把“已上市”解释为“FDA 批准适应症与 LMNA 相关”；范围只是候选集合。
- 不在本任务中改代码或提交 Hub 数据。

## 4. 匹配规则（核心）

### 4.1 规范化函数

```python
def canon_name(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s)).strip().lower()
    s = re.sub(r"[\s_]+", "-", s)       # 空格/下划线 -> 连字符
    s = re.sub(r"[^a-z0-9\-]", "", s)   # 去掉其余标点
    s = re.sub(r"-+", "-", s).strip("-")
    return s
```

示例：

- `trichostatin-a` ↔ `Trichostatin A` → `trichostatin-a`
- `LY-294002` ↔ `LY294002` → `ly294002`
- `17-beta-estradiol` ↔ `17β-estradiol`（NFKC 后仍需别名表处理 β）
- `KUC107191N` → `kuc107191n`（大小写不敏感）

### 4.2 盐型/水合物规则

只在“已知盐/水合物 token 位于名称末尾”时剥离，且要求剥离后的父名在 Hub 中存在；**不要无条件剥离 `acetate`、`succinate` 等可能是活性酯/前药的词**。

建议 token 列表（可配置）：

```
hydrochloride, hcl, hydrobromide, hbr, mesylate, mesilate, tosylate, besylate,
maleate, fumarate, tartrate, citrate, sulfate, sulphate, phosphate, acetate,
lactate, gluconate, sodium, potassium, calcium, magnesium,
dihydrate, monohydrate, hydrate, sesquifumarate, pamoate, embonate
```

风险示例：

- `betamethasone-acetate`、`cortisone-acetate`、`hydrocortisone-acetate` 是**酯**，不是盐；剥离会错误合并到母体。
- `abiraterone-acetate` 是前药；Hub 可能只列 `abiraterone-acetate`，而 LINCS 用 `abiraterone`。
- 处理方式：先尝试精确/规范化匹配；失败后再尝试“剥离一侧盐 token”的候选，并把 `match_method` 标为 `name_salt`、`confidence=medium`；对酯类建立显式排除表。

### 4.3 别名表（必须人工维护）

确定性别名（首批）：

| LINCS 名称 | Hub 名称 | 说明 |
|---|---|---|
| `paracetamol` | `acetaminophen` | 国际/US 名称 |
| `salbutamol` | `albuterol` | 国际/US 名称 |
| `sirolimus` | `rapamycin` | 同一化合物 |
| `fluorouracil` | `5-fluorouracil` | Hub 带位号 |
| `olmesartan-medoxomil` | `olmesartan` 或 `olmesartan-medoxomil` | 前药/母体，需保留两者 |
| `estradiol` / `17-beta-estradiol` | `estradiol` | 立体异构需人工确认 |

别名表放 `data/derived/drug_aliases_v1.csv`（`lin_name,hub_name,note`），每行需注明来源；不要用模糊字符串相似度自动合并（会把同靶点不同药物合并）。

### 4.4 匹配优先级

1. `pert_id` 的 BRD 基础 ID 精确匹配 → `match_method=pert_id`，`confidence=high`；
2. 规范化名称精确匹配 → `name_exact`，`high`；
3. 别名表 → `alias`，`high`（人工确认过）；
4. 单侧盐型剥离 → `name_salt`，`medium`；
5. InChIKey 匹配 → `inchi`，`high`（但只覆盖 832 个，作为交叉验证）；
6. 其余不纳入 `launched` 范围，记录到 `unmatched.csv` 供人工审阅。

## 5. 产物格式

```
<DATA_DIR>/derived/drug_scope_launched_v1/
├── drug_scope.csv          # 每行一个 LINCS 药物
├── unmatched.csv           # Hub Launched 中未能匹配的记录
├── aliases.csv             # 本次使用的别名表（复制一份，保证可复现）
└── manifest.json           # Hub 文件哈希/日期、LINCS 元数据哈希、计数
```

`drug_scope.csv` 列：

| 列 | 含义 |
|---|---|
| `lin_pert_id` | LINCS `pert_id`（BRD-...） |
| `lin_pert_iname` | LINCS `pert_iname` |
| `hub_pert_iname` | Hub 药物名 |
| `clinical_phase` | 固定 `Launched`（保留字段便于未来扩展） |
| `match_method` | `pert_id/name_exact/alias/name_salt/inchi` |
| `confidence` | `high/medium` |
| `hub_target` | Hub `target`（可选，展示用） |
| `hub_moa` | Hub `moa`（可选，L3 注释复用） |

`manifest.json` 至少记录：

- Hub 文件 URL、`!File_date`、SHA256；
- LINCS `sig_info` / `pert_info` 的 SHA256；
- 计数：Hub Launched 2,427；匹配药物 1,222；实例 36,573；未匹配 1,205；
- 别名表版本；生成时间；脚本版本。

注意：受许可证限制，以上文件**不提交 git**；仓库只提交生成脚本与本文档。若 D4 允许再调整。

## 6. 接口与代码改法

### 6.1 配置

```python
# backend/config.py
DRUG_SCOPE = os.getenv("LMNA_DRUG_SCOPE", "all")          # all | launched
DRUG_SCOPE_FILE = os.getenv("LMNA_DRUG_SCOPE_FILE", "")   # launched 时必填
```

启动时：

- `all`：行为完全不变；
- `launched`：文件不存在或为空 → 启动失败并给出明确错误（不要静默回退到全部，避免用户误以为在看已上市药物）；
- 校验 `drug_scope.csv` 中每个 `lin_pert_id` 都能在 `sig_info` 中找到；不匹配的条目记录 warning。

### 6.2 `L5Provider`

- `get_drug_samples()`：`launched` 时过滤 `pert_id.isin(scope_ids)`；实例数从 205,034 降到 36,573。
- `get_drug_name_map()`：只返回范围内映射。
- `list_available_drugs()`（新增，可选）：返回 `(n_drugs, n_instances, scope)`，供 `/api/health` 与前端显示。
- 注意：`pert_iname` 为空的实例仍按现有逻辑跳过；`BRD-...` 作为名称的未命名化合物如果通过 ID 命中，保留其 `pert_iname`（可能是 ID 本身），在 UI 上显示为 ID。

### 6.3 药物中位数缓存

- 缓存文件名加入范围与版本：`_drug_median_matrix.launched_v1.npy`、`_drug_names.launched_v1.csv`；
- 缓存 key 包含 `manifest.json` 的 SHA256 或 `scope_file_sha256`；
- 切换范围不会复用旧缓存；构建时间约 4 分钟（按全部药物 205,034 实例、keji 实测外推；launched 36,573 实例约 1 分钟以内）；
- 与 L2（缓存失效与版本）一起上线；旧 `all` 缓存保留。

### 6.4 API / 前端

- `GET /api/health` 增加：`drug_scope`, `n_drugs`, `n_instances`, `scope_source`（`all`/`launched`/`touchstone_fallback`）。
- `GET /api/drugs/scope`（可选）返回范围元数据与许可证提示。
- `/api/genes/{gene}/drugs` 的响应增加 `drug_scope` 与 `n_drugs` 字段（只加字段，不改名）。
- 前端在结果页显示“候选药物范围：全部化合物（19,811）/ 已上市（1,222，匹配覆盖 17.8%）”，并附许可证/数据来源说明。
- 导出 CSV 增加 `drug_scope` 列或在表头注明。

### 6.5 与 L4 的关系

药物范围改变后：

- 排序的分母从 19,811 变为 1,222；
- 若 L4 的 null/FDR 按药物集合生成，必须用同一范围重建 null 分布；
- `p/FDR` 不能直接沿用 `all` 范围的结果；
- 前端不能把两个范围的 p 值放在一起比较。

## 7. 迁移步骤

1. 人工确认 D4 许可结论（见 §9）。若不允许，停止；退化到 `is_touchstone` 方案需另写文档。
2. 在部署环境下载 Hub 2020-03-24 两个文件；计算 SHA256；记录 `!File_date`。
3. 运行匹配脚本（实施阶段新增），生成 `drug_scope.csv` / `unmatched.csv` / `manifest.json` 到 `cache/` 或服务器数据目录。
4. 人工抽检：
   - 随机 50 个 `pert_id` 命中，核对 Hub 名称与 LINCS 名称；
   - 全部 `name_salt` 和 `alias` 命中逐条核对；
   - 检查 `unmatched.csv` 中是否有明显应匹配项（如 `5-fluorouracil`）。
5. 设置 `LMNA_DRUG_SCOPE=launched`、`LMNA_DRUG_SCOPE_FILE=...`，启动 API；确认 `/api/health` 计数为 1,222 左右。
6. 重建药物中位数缓存；跑 5 个已知基因的 top/bottom 列表，与 `all` 模式对比，记录变化。
7. 若启用 L4，重跑该范围的 null/FDR 校准。
8. 回滚：`LMNA_DRUG_SCOPE=all`，重启；旧缓存仍在。
9. 前端灰度：先只显示范围说明，不改变默认；确认后再允许切换。

## 8. 验收清单（实施时执行）

- [ ] `clinical_phase == "Launched"` 计数为 2,427（2020-03-24 文件）。
- [ ] 匹配产物计数可复现：ID 968、名称 1,177、并集 1,221、实例 36,573（允许因别名表新增而变化，需在 manifest 记录）。
- [ ] 每个 `lin_pert_id` 在 `sig_info` 中存在；无重复；`match_method` 分布可审计。
- [ ] 盐型规则单测：`betamethasone-acetate` 不被错误剥离；`imatinib-mesylate` 能匹配到 `imatinib`。
- [ ] 别名表单测：paracetamol/acetaminophen、salbutamol/albuterol、sirolimus/rapamycin、fluorouracil/5-fluorouracil。
- [ ] `all` 模式行为与改动前完全一致（回归测试）。
- [ ] `launched` 模式启动时文件缺失/损坏能明确报错，不静默回退。
- [ ] 药物中位数缓存按范围隔离，切换不会读到旧缓存。
- [ ] `/api/health`、`/drugs` 返回范围与计数；API 只加字段。
- [ ] L4 的 FDR 使用同范围 null；跨范围结果不混用。
- [ ] 前端/导出明确显示数据来源与非商业使用限制。

## 9. 待人工确认（D4 许可）

1. **许可结论**：Hub 文件头写“non-commercial use only”；二手资料称 CC BY 4.0。两者冲突。请确认：
   - LMNA 是否属于非商业科研用途？
   - 是否允许在公开仓库中提交“由 Hub 派生的已上市药物列表”？
   - 是否需要在 UI/导出中附完整 citation 与免责声明？
2. 若不允许提交派生列表：接受“部署时本地生成、不入 git”的方案吗？
3. 若 Hub 不可用：是否接受 `is_touchstone=1`（2,429 个化合物）作为近似？它与 `Launched` 不等价（Touchstone 包含部分临床/工具化合物）。
4. 默认范围是否保持 `all`？建议保持，避免改变现有结果。
5. 是否把 `hub_moa` 一并写入范围文件，供 L3 注释复用（会扩大派生数据的范围，需许可确认）。

## 10. 工作量估算

| 工作 | 人日 |
|---|---|
| 匹配脚本 + 规范化/盐型/别名 + 单测 | 1.0 |
| 范围文件生成 + 人工抽检 | 0.5 |
| Provider/缓存/API 改造 + 回归测试 | 0.5–1.0 |
| 前端范围提示 + 导出 | 0.25 |
| L4 范围重校准（若同时启用） | 0.5 |
| 许可/文档/评审 | 0.25 |
| **合计** | **3.0–3.5 人日**（不含许可等待） |

## 11. 发现但未处理

- GSE92742 中约一半 `Launched` 药物没有可用 profile；这不是代码能解决的，需要换用 GSE70138/LINCS2020 或接受覆盖缺口。
- `pert_iname` 存在少数大写/ID 形式（如 `KUC107191N`）；未命名化合物需要用 `pert_id` 展示。
- Hub 2020 与 2025 版本的 `Launched` 计数接近，但具体条目可能变化；升级需重跑并做差异审阅。

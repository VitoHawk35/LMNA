# L7d · 备选签名来源（trt_oe / trt_xpr / 用户上传差异基因）（设计文档）

- 状态：方案待人工确认（只出文档，未实施）
- 基线：LMNA `main` @ `315f965`
- 关联：L3（`mode=lof|gof`、判档 `qc` 字段）、L7a（数据层）、L7b（实例级打分）

## 1. 结论摘要

论文的“多证据融合”需要三类补充证据：

1. **过表达（trt_oe）**：GSE92742 已有，**22,205 个实例、3,114 个 `pert_iname`、10 个细胞系**，与 shRNA 共用现有 473,647 列矩阵，不需要新数据；但方向与 shRNA 相反，必须显式按 `mode=gof` 处理。
2. **CRISPR（trt_xpr）**：GSE92742 没有；GSE70138 有 **3,882 个签名、353 个 perturbagen、53 个唯一基因、11 个细胞系**。GSE70138 Level5 文件 5.37 GB（118,050×12,328），只需提取 978 landmark × 3,882 签名 ≈ **15 MB** 的派生层。数据量不大，但需要一次性下载/解析 5.37 GB。
3. **用户上传差异基因**：不依赖 L1000 矩阵，只要基因符号能映射到 978 landmark；XSUM/WTCS 都只需要 up/down 基因列表，因此这是成本最低、最贴近疾病证据的来源。需要严格的格式校验、大小限制和“不能作为唯一证据”的提示。

与 L3 的衔接：

- `mode` 已经由 L3 定义为 `lof|gof`：shRNA/CRISPR 敲除 = `lof`，过表达/CRISPR 激活 = `gof`；
- L3 的 `qc` 是判定“这条签名能不能用”的唯一门槛；本方案只新增 `source`、`provenance`、`concordance` 三个字段，**不改变 L3 现有判档规则**；
- 多来源的“共同指向”只作为展示/排序加权，不单独产生 p 值；药物级显著性仍走 L4。

推荐分三期：先做 `trt_oe`（数据已在手）→ 再做用户上传（产品价值最高）→ 最后做 `trt_xpr`（需要下载/集成 GSE70138）。

## 2. 数据与代码事实

### 2.1 现有矩阵里的 trt_oe

服务器 `sig_info` 统计（只读）：

| 项目 | 数值 |
|---|---|
| `trt_oe` 实例 | 22,205 |
| `trt_oe.mut` 实例 | 6 |
| 唯一 `pert_iname`（含突变体） | 3,114 |
| 细胞系 | 10 |
| 示例 | `ABL1`, `ABL1_G2A`, `ABL1_T315I`, `A2M`, `ABAT`, ... |

- 这些实例已经在 `fast_matrix.npy` 的 473,647 列中，L7a 的 landmark 层天然包含它们。
- 当前 `L5Provider` 只筛选 `trt_sh*`（`backend/l5_provider.py:85-87`）和 `trt_cp`（`:89-91`），没有 `trt_oe` 的查询方法。
- `pert_iname` 中的 `_G2A`、`_T315I` 等是突变体；做“基因级”签名时应默认只取野生型（无下划线后缀）或单独展示突变体。

### 2.2 GSE70138 的 trt_xpr

从 GEO 补充文件下载并核对（2026-10-17）：

| 项目 | 数值 |
|---|---|
| `GSE70138_Broad_LINCS_Level5_COMPZ_n118050x12328_2017-03-06.gctx.gz` | 5,365,179,698 B（5.37 GB） |
| Level3（345,976×12,328） | 13,540,497,238 B（13.54 GB） |
| `sig_info` 行数 | 118,050 |
| `trt_xpr` 签名数 | 3,882 |
| `trt_xpr` perturbagen 数 | 353 |
| `trt_xpr` 唯一基因（`pert_iname`） | 53 |
| `trt_xpr` 细胞系 | 11（A375.311, A549.311, HA1E.101/311, HELA.311, HT29.311, MCF7.101/311, PC3.101/311, YAPC.311） |
| 基因示例 | ACLY, AKT1, AKT2, AURKB, AXL, BCL2L1, BRAF, ... TP53, ZEB1 |

说明：

- 这 53 个基因是 CRISPR 工具覆盖的基因，不等于“所有基因都有 xpr 证据”；多数查询基因仍只有 shRNA。
- `trt_xpr` 的具体方向（敲除/激活）需要按 `pert_info` 与实验元数据逐条确认；在确认前，默认按 `lof` 处理并在 `provenance` 标注 `direction_unverified`。
- GSE92742 的 Level5 与 GSE70138 的 Level5 都使用 12,328 基因空间、978 landmark；合并时按 `sig_id` 与 `cell_id` 建独立映射，不要假设 ID 格式一致。

### 2.3 用户上传

- 输入：CSV/TSV，至少两列 `gene,log2fc`（可选 `p_value,fdr`）；
- 基因符号需映射到 978 landmark；大小写不敏感，但同义符号（如 `TP53` vs `P53`）需要别名表或拒绝；
- 阈值默认：`|log2FC| >= 1` 且（若提供）`FDR < 0.05`；上下调各至少 5 个基因，最多各 500 个；
- 输出：标准 signature JSON，`source="user_deg"`，`mode` 由用户选择（疾病 signature 通常是“疾病 vs 正常”，逆转逻辑与 `lof` 相同，但必须在 UI 解释）；
- 隐私：不上传到第三方；不写入公共缓存；任务结果按用户/会话隔离（L7f 的 DB 需要 `owner_id`）。

## 3. 统一签名/证据模型

建议在现有 signature dict 上增加字段（只加不改）：

```json
{
  "signature_id": "sha256:...",
  "gene_name": "LMNA",
  "mode": "lof",
  "source": "l5_shrna",
  "source_detail": {
    "pert_type": "trt_sh",
    "n_instances": 36,
    "n_hairpins": 4,
    "cell_lines": ["A549", "MCF7"],
    "dataset": "GSE92742",
    "data_version": "landmark_v1"
  },
  "n_samples": 36,
  "up_genes": ["..."],
  "down_genes": ["..."],
  "qc": { "grade": "green", "loho_jaccard_min": 0.58, "...": "..." },
  "concordance": {
    "with": ["l5_oe"],
    "up_jaccard": 0.31,
    "down_jaccard": 0.27,
    "ks_pearson": 0.62,
    "verdict": "partial"
  }
}
```

约束：

- `signature_id` 由规范化内容（gene、mode、source、up/down 集合、数据版本、符号约定版本）哈希得到；同一内容多次上传得到同一 ID。
- `qc` 由 L3 生成；本方案不覆盖。
- `concordance` 只在有两种以上来源时计算，缺失时为 `null`。

## 4. 各来源的实现设计

### 4.1 trt_oe

**Provider**

```python
# L5Provider 新增
def get_oe_samples(self, gene_name: str, include_mutants: bool = False) -> pd.DataFrame:
    df = self._oe_df
    if not include_mutants:
        df = df[~df.pert_iname.str.contains("_", na=False)]
    return df[df.pert_iname.str.upper() == gene_name.strip().upper()].copy()
```

- 在 `__init__` 中缓存 `_oe_df = sig_info[pert_type == "trt_oe"]`。
- `list_available_genes()` 是否包含 OE-only 基因：建议新增 `list_available_genes(source=...)` 或在 `/api/genes` 返回 `sources` 字段；不改变现有默认（仍以 shRNA 为准）。

**签名**

- 复用 `SignatureEngine` 的 ranks + KS + bootstrap；
- 方向：OE 的 KS 符号与 shRNA 相反。实现上不要复制一套算法，建议在 `compute_signature(gene, source="oe")` 中：
  - 取 OE 样本；
  - 计算 `ks_oe`；
  - 输出时 `up_genes/down_genes` 按 `mode=gof` 的语义翻转（或保留原始 KS，由前端按 mode 解释）。
- 具体翻转规则必须与 L1 的符号约定一起定义，并在签名 JSON 中记录 `sign_convention_version`。

**接口**

- `POST /api/genes/{gene}/compute` 增加 `source: Literal["shrna","oe"] = "shrna"`（默认不变）；
- 缓存文件名加入 `source`；`/api/genes/{gene}/signature?source=oe`；
- `/api/genes/{gene}/status` 返回每种来源的样本数。

**工作量**：2–3 人日（含方向校准与测试）。

### 4.2 trt_xpr

**数据准备**

1. 下载 `GSE70138_Broad_LINCS_Level5_COMPZ_n118050x12328_2017-03-06.gctx.gz`（5.37 GB）与 `sig_info`/`pert_info`（各约 2 MB / 82 KB）；
2. 用 cmapPy（或现有 gctx 解析工具）只提取 978 landmark 行 + `trt_xpr` 列，得到 `(3,882, 978)` float32 ≈ **15 MB**；
3. 写 `xpr_v1/`：`xpr_sigs.npy`、`sig_ids.csv`、`pert_info.csv`（基因、细胞系、方向、数据集版本）、`manifest.json`；
4. 与 L7a 的 landmark 层拼接时，不要覆盖原层；新增 `source` 维度（`sig_source` 列：`l5_gse92742` / `l5_gse70138_xpr`）。

**Provider**

- 新增 `XprProvider`（或 `L5Provider` 的 `source` 分支），实现 `IDataProvider` 的必要方法；
- `get_shrna_samples` 对 xpr 返回 CRISPR 样本；`get_expression_matrix` 从 `xpr_sigs.npy` 读取；
- `get_drug_samples` / 药物打分不由 xpr 提供，委托 L5 或抛 `NotImplementedError`（与接口文档一致）。

**方向**

- `trt_xpr` 通常是 CRISPR 敲除（loss-of-function），按 `mode=lof`；
- 若数据中包含 CRISPR 激活（CRISPRa），必须逐条标注为 `gof`；在未确认前不要混合；
- 与 shRNA 的 `up/down` 语义对齐后，才能计算 concordance。

**覆盖**

- 只有 53 个基因有 xpr 数据；其他基因仍只有 shRNA/OE。UI 必须显示“该基因无 CRISPR 证据”，不能把缺失当阴性。

**工作量**：5–8 人日（下载/解析 1–2 天，Provider/方向/测试 3–5 天，文档 1 天）。

### 4.3 用户上传

**API**

```
POST /api/signatures/upload
Content-Type: multipart/form-data
fields:
  file: CSV/TSV (<= 1 MB, <= 5,000 rows)
  gene_name: string (optional, default "UPLOAD")
  mode: "lof" | "gof"
  log2fc_threshold: float = 1.0
  fdr_threshold: float = 0.05
response:
  { "signature_id": "...", "n_up": 120, "n_down": 98,
    "n_unmapped": 12, "unmapped_examples": ["..."], "qc": {...} }
```

**校验**

- 必需列：`gene`、`log2fc`；`p_value`/`fdr` 可选；
- 基因符号统一大写、去空格；只保留 978 landmark；记录未映射数量与前 20 个示例；
- 上下调各至少 5 个、最多 500 个；不足/超限返回 422 并说明；
- 拒绝重复基因（保留 |log2FC| 最大的一行并 warning）；
- 文件类型白名单（`.csv/.tsv/.txt`），禁止公式注入字符（`= + - @` 开头）在导出时转义；
- 结果只返回 top/bottom，不回传完整上传内容；日志不记录原始行。

**存储**

- `cache/signatures/upload/<signature_id>.json`：只存 up/down 列表、阈值、来源、时间、owner；
- 不存原始 CSV；如需审计，存哈希与计数；
- 与 L7f 的 DB 结合时，`owner_id` 必填，防止跨用户读取。

**打分**

- XSUM/WTCS 只需要 up/down 列表，因此上传签名可以直接复用 `DrugScorer`，不需要新的矩阵读取；
- `mode=lof`：与 shRNA 相同的逆转逻辑；`mode=gof`：按 L3 定义反向排序；
- 结果页必须显示“证据来源：用户上传差异表达；未经 L1000 实验验证”。

**工作量**：3–4 人日（含前端上传与错误提示）。

## 5. 与 L3 判档的衔接

L3 当前的判档输入是 `precheck + signature + annotation`，输出 `qc.grade`。本方案建议的扩展（不改变现有规则）：

1. `precheck(provider, gene, source="shrna")` 增加 `source`，返回该来源的 `n_samples/n_hairpins/n_cells`；
2. `grade()` 的 `reference` 字段增加 `source`、`mode`、`concordance`（只展示，不判档）；
3. 未来的 v2 规则（需人工确认后才改）可以是：
   - `green`：shRNA LOHO ≥ 0.5，且（若有 OE/xpr）concordance 不为 `conflicting`；
   - `yellow`：shRNA 稳定但次要来源 `partial/conflicting`；或只有 OE 且 LOHO 无法计算；
   - `red`：只有用户上传且无任何实验证据；或 `n_sig < 5`；
4. 在 v2 规则落地前，`qc` 仍只由 shRNA 决定；多来源信息只作为结果页的“证据卡片”。

**concordance 计算**

- 取两种来源各自 |KS| 前 k 个基因（k = max(10, n_up+n_down)，封顶 200）；
- 分别计算 up-up、down-down 的 Jaccard；
- 对共同基因的 KS 向量做 Pearson（方向对齐后）；
- `verdict`：
  - `concordant`：up/down Jaccard 均 ≥ 0.2 且 KS Pearson ≥ 0.3；
  - `partial`：任一指标为正但未达阈值；
  - `conflicting`：up-up 与 down-down 同时为负相关，或方向相反；
  - `insufficient`：共同基因 < 10。
- 这些阈值是初始建议，需在夹具上校准；不要对外宣称生物学验证。

## 6. 多来源联合排序（展示层）

- 对同一基因，分别得到 `shrna`、`oe`、`xpr`、`user_deg` 的药物排名；
- 只在各来源都进入前 10% 的药物上打“多来源支持”徽章；
- 排序可用排名聚合（如 median rank 或 RRA），权重建议：shRNA 1.0、xpr 0.8、oe 0.6、user_deg 0.8（可配置）；
- **不**把多个来源的 p 值简单相乘/取最小；药物级 FDR 仍由 L4 在选定主来源上计算；
- UI 必须能展开查看每个来源的排名，避免“黑箱共识”。

## 7. 迁移步骤

### 7.1 trt_oe（第一期）

1. 新增 `_oe_df` 与 `get_oe_samples`；单测覆盖突变体过滤。
2. `SignatureEngine` 支持 `source="oe"`；与 L1 确认方向后写死符号约定版本。
3. API `source` 参数、缓存 key、前端来源选择。
4. 用 5 个基因（如 ABL1、EGFR、MTOR、CDK4、TP53）对比 OE 与 shRNA 的签名 concordance，记录结果。

### 7.2 用户上传（第二期）

1. 新增上传 endpoint、校验、存储；限制 1 MB/5,000 行。
2. 复用 `DrugScorer`；结果页显示来源与免责声明。
3. 与 L7f 的 `owner_id`/任务表一起上线；无 L7f 时先用临时 `upload_id`。
4. 端到端测试：正常 CSV、缺列、超限、全未映射、重复基因、公式注入。

### 7.3 trt_xpr（第三期）

1. 下载 GSE70138 Level5 与元数据；校验 SHA/行数。
2. 提取 978 landmark × trt_xpr 列，生成 `xpr_v1`（15 MB）。
3. 逐条确认方向；先只启用 `lof`，`gof` 留空。
4. Provider + API `source="xpr"`；结果页显示 53 个基因的覆盖限制。
5. 与 shRNA 的 concordance 抽检 10 个基因。

## 8. 验收清单（实施时执行）

- [ ] `trt_oe` 样本数/基因数与 `sig_info` 一致（22,205 / 3,114；野生型过滤后数量单独记录）。
- [ ] OE 签名方向在 5 个已知基因上与 shRNA 的预期关系一致（或明确记录翻转规则）。
- [ ] 用户上传：正常/缺列/超限/未映射/重复/公式注入 6 类测试通过。
- [ ] 上传签名不落原始 CSV；跨用户不可读。
- [ ] `trt_xpr` 提取后形状 `(3882, 978)`、float32、约 15 MB；53 个基因、11 个细胞系计数一致。
- [ ] `trt_xpr` 方向标注完整；未确认方向的数据不参与打分。
- [ ] `concordance` 在合成数据上的 Jaccard/Pearson/verdict 与手算一致。
- [ ] L3 现有判档结果不受影响（回归）。
- [ ] API 只加字段；默认 `source="shrna"` 行为不变。
- [ ] 缺失来源在 UI 显示“无数据”，不显示为阴性。

## 9. 工作量估算

| 工作 | 人日 |
|---|---|
| trt_oe Provider + 签名 + 方向 + 测试 | 2–3 |
| 用户上传 API + 校验 + 存储 + 前端 | 3–4 |
| trt_xpr 下载/提取 + Provider + 方向 + 测试 | 5–8 |
| concordance + 展示层 | 1–2 |
| 文档/评审 | 1 |
| **合计（三期）** | **12–18 人日** |

建议先做 1 + 2（5–7 人日），trt_xpr 等 L7b/L7e 的结论再决定。

## 10. 待人工确认

1. OE 的符号约定是否与 L1 的 shRNA 约定一致地翻转？由谁给出最终定义？
2. 用户上传是否对匿名用户开放？是否需要登录/配额（与 L7f 的 auth 一起考虑）？
3. trt_xpr 用 GSE70138（2017，53 个基因）还是等待 LINCS2020/更大覆盖？后者数据量与许可需另评估。
4. `concordance` 的阈值（0.2/0.3）是否接受先用建议值，后续在夹具上校准？
5. 多来源联合排序是否进入正式结果，还是只做展示徽章？

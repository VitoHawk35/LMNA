# task-L5 交付说明 · LMNA 前端（P1）

## 任务ID / 分支 / 基线提交

- 任务：`task-L5` · LMNA 前端（P1）
- 分支：`fix/L5-frontend`
- 基线：`origin/main` = `8d367b6`（Merge branch 'fix/L2-cache-versioning'）
- 工作目录：`D:\agent-workspace\worktrees\task-L5`
- 本波未 push 到 `main`；合并由用户在 GitHub 上审阅后进行。

## 改动文件（文件:行号范围）

| 文件 | 行号 | 改动 |
|---|---|---|
| `frontend/index.html` | 1-600（整体） | 换肤、同源 API、适用性卡片、mode 语义、FDR、XSS、进度条 |
| `frontend/index.html` | 6 | 标题改为“基因敲低签名与药物筛选” |
| `frontend/index.html` | 9-21 | 任务第 6 条给定 CSS **原样替换**；22-58 为补充样式（中性色、圆角、字重、档位徽标等） |
| `frontend/index.html` | 39 | `.text-success/.text-danger/.text-warning/.text-info` 统一为中性 `#171717` |
| `frontend/index.html` | 76 | 删除 `value="LMNA"`，仅保留 placeholder |
| `frontend/index.html` | 80-93 | mode 下拉：功能丧失（默认）/ 功能获得 / 不确定（按 lof） |
| `frontend/index.html` | 110-118 | 新增“基因适用性”卡片容器 |
| `frontend/index.html` | 128-137 | 新增快速模式警告条 |
| `frontend/index.html` | 196 / 212 | Top / Bottom 表新增 FDR 列（表头随 mode 切换） |
| `frontend/index.html` | 237 | `const API_BASE = '';`（同源相对路径） |
| `frontend/index.html` | 242-247 | 新增 `esc()` 转义函数 |
| `frontend/index.html` | 320-386 | `renderSuitability()`：绿 ✓ / 黄 ! / 红 ✗、reasons、参考信息折叠、红档替换按钮 |
| `frontend/index.html` | 388-443 | `submitTask()`：提交前先调 `/suitability`，红档拦截 |
| `frontend/index.html` | 445-488 | `pollTask()`：去掉写死 60%，显示后端 message + 不确定进度动画 |
| `frontend/index.html` | 490-558 | 药物行渲染、FDR (<0.05 行 500 字重)、按 mode 的标题/说明、fast_mode 警告 |
| `backend/main.py` | 4 | 模块 docstring 改为通用名 |
| `backend/main.py` | 16 | 引入 `StaticFiles` |
| `backend/main.py` | 29 | FastAPI title 改为 `Gene Knockdown Signature & Drug Screening System` |
| `backend/main.py` | 307-315 | 在所有 `/api` 路由之后 mount `PROJECT_ROOT/frontend`（`html=True`） |
| `backend/config.py` | 4 | 模块 docstring 改为通用名 |
| `backend/tests/test_api_health.py` | 46-53 | 新增同源部署回归测试：`/` 返回 index.html 且 `/api` 不被遮蔽 |
| `deliveries/task-L5.md` | 新增 | 本文件 |

未改包名、仓库名、内部变量名、环境变量名（`LMNA_*` 保留）。

## 测试 / 核对

### 1. 后端 pytest（夹具模式）

夹具来源：`D:\agent-workspace\deliveries\task-L0\fixtures`（L0 生成，未提交）。
conftest 在 import 后端模块前设置 `DATA_PROVIDER=fixture`、`LMNA_TASK_INLINE=1`、
临时 `LMNA_CACHE_DIR`、`BOOTSTRAP_N=200`、`DRUG_NULL_N=200`；夹具目录由外部
`LMNA_FIXTURE_DIR` 提供（读 `backend/tests/conftest.py`）。

执行命令（在 `backend/` 目录）：

```bash
LMNA_FIXTURE_DIR='D:/agent-workspace/deliveries/task-L0/fixtures' \
  D:/mine_Anaconda3/python.exe -m pytest tests -q -rs
```

摘要：

```
129 passed, 1 skipped, 6 warnings in 33.92s
SKIPPED [1] tests/test_fixture_regression.py:132:
  D3: 未提供 Table S1（backend/tests/fixtures/table_s1.tsv）
```

跳过项与本次改动无关（缺 D3 的 Table S1）。完整日志：
`D:\agent-workspace\deliveries\task-L5\pytest_with_fixture.log`。

### 2. uvicorn 同源部署

在 `backend/` 目录启动（夹具模式）：

```bash
DATA_PROVIDER=fixture \
LMNA_FIXTURE_DIR='D:/agent-workspace/deliveries/task-L0/fixtures' \
LMNA_CACHE_DIR='D:/agent-workspace/deliveries/task-L5/runtime-cache' \
BOOTSTRAP_N=200 DRUG_NULL_N=200 LMNA_TASK_INLINE=1 \
D:/mine_Anaconda3/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8765
```

核对结果：

- `GET /` → 200，返回 `frontend/index.html`，标题“基因敲低签名与药物筛选”。
- `GET /api/health` → 200，`provider=fixture`，`available_genes=1971`（证明 `/api/*` 未被 StaticFiles 遮蔽）。
- `GET /api/genes/CDK4/suitability` → 200，`precheck.data_gate_ok=true`、86 样本 / 7 hairpin / 11 细胞系。
- `POST /api/genes/CDK4/compute` `{"method":"xsum","mode":"lof"}` → 任务完成；签名 50 up / 50 down，`qc.grade=green`，`fast_mode=false`；top 50 / bottom 50。
- `POST .../compute {"method":"xsum","mode":"gof"}` → `mode=gof`，top1 `KPT-185`（score −279.9931，`fdr_mimic=0.029785`）。
- `POST .../compute {"method":"wtcs","mode":"lof"}` → `method=wtcs`，`fdr_*` 全为 `None`，页面显示 `—`。
- `POST .../compute TOP2A` → `qc.grade=red`，药物列表为空（L3 红档屏蔽）。

### 3. 浏览器自动化（Chrome CDP 9222 + playwright-core）

通过 browser skill 连接本机独立 Chrome，实际打开 `http://127.0.0.1:8765/`
完成以下手工路径（脚本在 `C:\Users\12705\.claude\skills\browser\scripts\task-l5-*.mjs`）：

1. 输入 `CDK4` → 点“检查数据” → 适用性卡片显示 `? 待判档` + 数据前置检查与 reasons（首次无缓存签名，`/suitability` 的 `qc=null`，后端无法只凭 precheck 给出稳定性档位；这是 L3 现状，未臆造字段）；截图 `01_suitability.png`。计算完成后重新检查同一基因，卡片显示 `✓ 绿档（已有缓存签名）`；截图 `01b_suitability_cached_green.png`。
2. 点“开始分析”→ 等待完成 → 标题 `逆转药物（lof）`、说明“分数越高，逆转越强；FDR 越小越可信”、FDR 表头 `FDR（逆转）`、首行 `GW-788388 / 45.312 / 0.018798`，FDR<0.05 行 computed font-weight = 500；计算完成后适用性卡片用签名 `qc` 刷新为 `✓ 绿档`（见 `02_results_lof.png` 顶部）。截图 `02_results_lof.png`。
3. 切换 `gof` 再计算 → 标题 `模拟药物（gof）`、说明“分数越低，模拟越强；FDR 越小越可信”、FDR 表头 `FDR（模拟）`；截图 `03_results_gof.png`。
4. 切到“不确定”→ 显示提示“按功能丧失（lof）计算；适用性档位最多显示为黄档”，绿档被显示为 `! 黄档`；截图 `04_uncertain_notice.png`。
5. 输入 `ABHD4`（1 个 hairpin）→ 红档，按钮文案变为“改用差异表达上传（cmap）”且 disabled；截图 `06_red_precheck.png`。
6. 先计算 `TOP2A`，再输入 `TOP2A` → 使用缓存签名 qc 判红（LOHO Jaccard=0.258 < 0.3），同样替换按钮；截图 `07_red_cached.png`。
7. WTCS 结果：`FDR` 列全部为 `—`，行无 significance class；截图 `09_wtcs_fdr_none.png`。
8. 快速模式：另起服务 `KS_THRESHOLD=2.0 FAST_MODE_TOP_N=10`，CDK4 结果 `fast_mode=true`、`qc.grade=red`；将真实任务结果交给 `showResults()`，警告条显示；截图 `08_fast_mode_banner.png`。
9. 进度条：另起非 inline 服务（`BOOTSTRAP_N=5000 DRUG_NULL_N=5000`），MTOR 计算期间捕获：
   - 提交后：width=100%、class=`progress-bar progress-bar-striped progress-bar-animated`、message=“任务已提交，等待执行...”（截图 `10_progress_submitted.png`）
   - running：后端 message=“开始计算签名...”，动画保留（截图 `11_progress_running.png`）
   - completed：message=“计算完成”，class 退回 `progress-bar`（截图 `12_progress_completed.png`）
   全程未出现写死的 60%。

浏览器日志：`browser_check.log`、`red_check.log`、`fastmode_check.log`、`wtcs_check.log`、`progress_check.log`。
截图清单（均在 `D:\agent-workspace\deliveries\task-L5\`，不入 git）：
`01_suitability.png`、`01b_suitability_cached_green.png`、`02_results_lof.png`、
`03_results_gof.png`、`04_uncertain_notice.png`、`05_xss_escaped.png`、
`06_red_precheck.png`、`07_red_cached.png`、`08_fast_mode_banner.png`、
`09_wtcs_fdr_none.png`、`10_progress_submitted.png`、`11_progress_running.png`、
`12_progress_completed.png`。

### 4. XSS 验证

为避免污染共享夹具，复制一份夹具到 `deliveries/task-L5/fixture-xss/`，只把
`lmna_fixture_cp.tsv` 中药物 `GW-788388` 的 `pert_iname` 改为
`<img src=x onerror=alert(1)>`（保持行数/矩阵列数不变），用独立缓存与端口 8766 启服务，
在真实浏览器中完成 CDK4 计算：

```
IMG_COUNT=0
SCRIPT_COUNT=0
DIALOGS=[]
PAYLOAD_VISIBLE_AS_TEXT=true
FIRST_HTML: <td>&lt;img src=x onerror=alert(1)&gt;</td>
```

结论：payload 只作为文本显示，未生成 `img` 元素，`onerror` 未执行（无 dialog）。
截图 `05_xss_escaped.png`。验证后已删除夹具副本与 XSS 缓存；
原夹具 `lmna_fixture_cp.tsv` 的 SHA256 仍为
`22b657091e954921dcb383a8d7188829a26b83c7ab01140e9c8e7dabacdf10d1`，
`onerror` 计数为 0，GW-788388 行完好。

## 附录一：报告 3.7 节验收清单逐条核对

- [x] 页面背景纯白、无渐变：computed `body.background-color=rgb(255,255,255)`，`.header` 背景纯白且 `background-image=none`。
- [x] 每个视图最多 1 个绿色实心按钮：仅“开始分析”为 `btn-primary`；其余为 outline/中性色。绿底文字 `#171717`。
- [x] 承载信息的文字不浅于 `#707070`：正文/次要文字为 `#171717` / `#707070`；未使用 Bootstrap 的 `text-muted`/`text-info` 浅色。**未跑 axe/Lighthouse**，以计算样式核对。
- [x] 按钮圆角 6、卡片圆角 12、无胶囊按钮：computed `border-radius: 6px` / `12px`。
- [x] 字重不超过 500：遍历可见元素 computed `max(font-weight)=500`；`strong/b/h1-h6` 均显式设为 500。
- [~] 绿色不表达数据含义：分数列已全部改为中性 `#171717`，上调=品红 `#b0004a`、下调=靛蓝 `#0438c4`；但档位徽标按任务第 3 条要求使用绿/黄/红（绿档 `✓`），与附录二存在冲突，见“待人工确认”。
- [—] 每张图一句解读、可导出 SVG/CSV：本页无图表（仅表格与基因标签），SVG 不适用；保留原有 JSON/CSV 导出。按本波范围未新增“导出 / FDA”按钮。
- [x] 所有数字等宽：`body { font-variant-numeric: tabular-nums; }`，分数/FDR 用 `ui-monospace`。
- [ ] 内网断网时字体与图表正常加载：Bootstrap CSS 仍来自 jsDelivr CDN（第 7 行），断网时组件样式会降级；D9 待人工决定是否放入 `frontend/vendor/`。

## 待人工确认（🧑‍⚖️）

- **D2 部署形态**：当前按同源部署实现：`API_BASE=''`，FastAPI 在 `/` mount 前端；
  `LMNA_CORS_ORIGINS` 为空时不启用 CORS。若生产走 nginx 反代，需确认 `/api` 转发规则，
  前端相对路径无需改动。请确认生产是“直连 8001”还是“nginx 反代”。
- **D9 是否本地化 Bootstrap**：建议内网断网场景把 Bootstrap CSS 放到 `frontend/vendor/`；
  本波未做，以免在未确认部署形态前引入额外静态资源。
- **档位徽标用色**：任务第 3 条要求绿 ✓ / 黄 ! / 红 ✗，附录二要求绿色不承载数据含义。
  当前档位徽标按任务第 3 条执行；如以附录二为准，可改为中性徽标 + 文案。
- **gof 说明文字**：lof 使用任务原文“分数越高，逆转越强；FDR 越小越可信”；
  gof 按实际语义改为“分数越低，模拟越强；FDR 越小越可信”（否则会误导）。
  如需严格统一原文，请确认。
- **不确定模式**：前端映射为 lof 提交，档位最多显示黄档；后端 mode 枚举仍只有 lof/gof。

## 发现但未处理

1. **导出 / FDA 按钮**：按本波范围不新增（属另一个待定移植任务）；页面保留原有 JSON/CSV 导出。
2. **无图表**：因此“每张图一句解读 + SVG 导出”在本页不适用；未新增 SVG 导出。
3. **Bootstrap CDN**：见 D9；断网时自定义 CSS 仍生效，但栅格/表格/按钮基础样式会退化。
4. **未缓存基因的档位**：`/api/genes/{gene}/suitability` 在无缓存签名时 `qc=null`、`grade=null`，
   前端只能显示“待判档”+ 数据前置检查 reasons；判档需先计算签名。这是 L3 后端现状，未改 API。
5. **fast_mode 正常 UI 不可达**：fast mode 会同时判红，而红档会禁用提交；本波用真实 fast-mode
   任务结果调用 `showResults()` 验证警告条。生产按 L1 后不应出现。
6. **WTCS 无 null 统计**：`fdr_*` 为 `None` 时显示 `—`，不做显著性加粗；属预期。
7. **placeholder 仍含 LMNA 示例**：任务要求保留 placeholder，故未删；“去 LMNA 写死”针对标题与默认值。
8. **`LMNA_*` 环境变量名**：`backend/main.py` 的 403 文案仍含 `LMNA_ADMIN_TOKEN`，因其是配置变量名，
   按“不要改内部变量名”保留。
9. **未跑 axe/Lighthouse**：附录一对比度项以 computed 样式核对，未引入额外审计工具。

# D3 旧页面与杂项（LMNA 部分）— 交付说明

- 任务ID：D3（R8、R13）
- 分支：`fix/D3-cleanup`
- 基线：`origin/main` @ `2e371c2`
- 改动文件：
  - `frontend/index.html`：Bootstrap 由 CDN 改为本地文件（CDN 备选保留为注释）
  - 新增 `frontend/bootstrap.min.css`（Bootstrap v5.3.0 官方 MIT 发行版，232,919 B，与 cmap 仓库 C4 本地化的文件逐字节一致）
  - 删除仓库根目录 5 张无关图片（见下）
- 未改动任何业务逻辑、API 字段与后端计算。

## 改动摘要

| 项目 | 位置 | 内容 |
|---|---|---|
| Bootstrap 本地化（R8） | frontend/index.html:7-9 | `<link href="https://cdn.jsdelivr.net/...">` 改为 `<link href="bootstrap.min.css">`；文件与 CDN 同为 v5.3.0，样式零差异；`backend/main.py:310-314` 已用 `StaticFiles(directory=frontend, html=True)` 托管整个 frontend/，无需后端改动 |
| 删除无关图片（R13） | 仓库根目录 | `3d19e0df....png`、`bc52be9a....png`、`bc5a99fb....png`、`e0d8d9f3....png`、`efddb0cd....jpg`（5 张哈希命名的截图类文件，删除前已全仓 grep 确认无任何引用） |

## 自测验收

1. **旧页面断网渲染** ✅：本地静态服务（`python -m http.server`，指向 `frontend/`）+ Playwright（Chromium），拦截全部非 127.0.0.1 请求模拟断网：
   - `.btn-primary` 计算样式 `background-color: rgb(62, 207, 142)`（#3ecf8e 绿底）、`color: rgb(23, 23, 23)`（#171717 近黑字）；
   - 栅格正常：`.row` 为 `display:flex; flex-wrap:wrap`，`.col-md-3` 宽 265px / 容器 1100px；
   - 外链请求 0 个、失败请求 0 个；本地 `bootstrap.min.css` 解析成功（`link.sheet.cssRules.length > 0`）。
   - 截图：`D:\agent-workspace\deliveries\task-D3\lmna-offline.png`；脚本与同次输出：`D:\agent-workspace\deliveries\task-D3\offline_check.js`。
2. **根目录无图片** ✅：`git ls-files | grep -icE '^[^/]*\.(png|jpg|jpeg|gif|bmp)$'` → `0`（全仓也无任何 png/jpg 在跟踪）。
3. **现有测试不回归** ✅：`LMNA_FIXTURE_DIR=D:\agent-workspace\deliveries\task-L0\fixtures D:\mine_Anaconda3\python.exe -m pytest backend/tests -q` → **129 passed, 1 skipped**（与基线一致；唯一 skip 为既有的 Table S1 未提供项，与本次改动无关）。

## 主agent验收命令

```bash
# LMNA 仓库 fix/D3-cleanup 分支
git ls-files | grep -icE '^[^/]*\.(png|jpg|jpeg|gif|bmp)$'   # 期望 0
grep -n 'bootstrap' frontend/index.html                       # 期望本地引用，CDN 仅在注释
LMNA_FIXTURE_DIR=D:\agent-workspace\deliveries\task-L0\fixtures D:\mine_Anaconda3\python.exe -m pytest backend/tests -q   # 期望 129 passed, 1 skipped
# 断网渲染复现：python -m http.server <port>（cwd=frontend/）后，
# node D:\agent-workspace\deliveries\task-D3\offline_check.js http://127.0.0.1:<port>/ <截图路径>
```

## 待人工确认项

- 无。

## 发现但未处理项

- 无。

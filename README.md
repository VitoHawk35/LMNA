> 📘 系统级交接文档（部署拓扑/三仓库现状/技术债/改进路线）：[docs/SYSTEM_HANDOFF.md](docs/SYSTEM_HANDOFF.md)

# LMNA

基因敲低（shRNA）签名构建与逆转药物预测系统。后端 FastAPI，前端纯 HTML/JavaScript。

## 文档

- 系统级交接（部署拓扑、三仓库关系、安全、性能、技术债、决策清单）：[docs/SYSTEM_HANDOFF.md](docs/SYSTEM_HANDOFF.md)
- LMNA 后端现状与字段级说明：[docs/BACKEND_SITUATION.md](docs/BACKEND_SITUATION.md)
- 各任务交付说明：[deliveries/](deliveries/)

## 快速定位

| 内容 | 路径 |
|---|---|
| 后端入口 | `backend/main.py` |
| 配置 | `backend/config.py` |
| 数据提供者 | `backend/l5_provider.py` |
| 签名/打分 | `backend/signature_engine.py`、`backend/drug_scorer.py` |
| 适用性判档 | `backend/suitability.py` |
| 前端 | `frontend/index.html` |
| 数据修复/复核脚本 | `scripts/fix_col_names.py`、`scripts/verify_drug_median.py` |
| 测试 | `backend/tests/` |

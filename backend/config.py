#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LMNA 基因特征系统配置
"""

import os

# 项目根目录（backend 的上级目录 = LMNA/）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# CMAP 项目根目录
CMAP_ROOT = os.path.dirname(PROJECT_ROOT)

# ============ 数据路径 ============
# 可通过环境变量覆盖，便于部署到服务器
DATA_DIR = os.getenv("CMAP_DATA_DIR", os.path.join(CMAP_ROOT, "cmap_data"))

# 核心数据文件
MATRIX_PATH = os.path.join(DATA_DIR, "fast_matrix.npy")
COL_NAMES_PATH = os.path.join(DATA_DIR, "col_sig_ids.csv")
ROW_NAMES_PATH = os.path.join(DATA_DIR, "row_gene_ids.csv")

# 原始元数据文件
SIG_INFO_PATH = os.path.join(DATA_DIR, "GSE92742_Broad_LINCS_sig_info.txt.gz")
GENE_INFO_PATH = os.path.join(DATA_DIR, "GSE92742_Broad_LINCS_gene_info.txt.gz")
PERT_INFO_PATH = os.path.join(DATA_DIR, "GSE92742_Broad_LINCS_pert_info.txt.gz")

# 矩阵维度（L1000  landmark genes × signatures）
N_GENES = 12328
N_SIGS = 473647

# 缓存目录（可用 LMNA_CACHE_DIR 覆盖，测试时指向临时目录）
CACHE_DIR = os.getenv("LMNA_CACHE_DIR", os.path.join(PROJECT_ROOT, "cache"))
SIGNATURE_CACHE_DIR = os.path.join(CACHE_DIR, "signatures")
DRUG_SCORE_CACHE_DIR = os.path.join(CACHE_DIR, "drug_scores")
TASK_CACHE_DIR = os.path.join(CACHE_DIR, "tasks")

# 确保缓存目录存在
for d in [SIGNATURE_CACHE_DIR, DRUG_SCORE_CACHE_DIR, TASK_CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

# ============ 签名计算参数 ============
# 最少 shRNA 样本数（D3：门槛是否过硬待用户确认，先用环境变量做成可配置）
MIN_SH_SAMPLES = int(os.getenv("MIN_SH_SAMPLES", "3"))
KS_THRESHOLD = float(os.getenv("KS_THRESHOLD", "0.2"))          # KS score 阈值（绝对值）
FDR_THRESHOLD = float(os.getenv("FDR_THRESHOLD", "0.05"))       # BH 校正后 P 值阈值（默认 0.05；论文模式 0.001 需同时设 BOOTSTRAP_N >= 100000）
BOOTSTRAP_N = int(os.getenv("BOOTSTRAP_N", "1000"))             # Bootstrap 次数（本地测试默认 1000，服务器 L3 建议 100000）
RANDOM_SEED = 42            # 随机种子

# 每个方向最多保留的签名基因数（按 |KS| 排序）；0 表示不封顶。
MAX_GENES_PER_DIRECTION = int(os.getenv("MAX_GENES_PER_DIRECTION", "50"))

# 快速模式：绕过统计显著性，直接取 |KS| 最大的 N 个基因作为 signature（仅用于前后端联调）
# 设置为 0 表示关闭（生产默认关闭）
FAST_MODE_TOP_N = int(os.getenv("FAST_MODE_TOP_N", "0"))

# ============ 药物筛选参数 ============
DEFAULT_TOP_K = 50
DEFAULT_BOTTOM_K = 50

# 药物级随机签名 null 的随机签名数（L4）。
# p 值的分辨率下限为 1/(DRUG_NULL_N+1)；BH-FDR 还受药物数影响，见 deliveries/task-L4.md。
DRUG_NULL_N = int(os.getenv("DRUG_NULL_N", "10000"))

# ============ API 配置 ============
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8001"))

# ============ 数据提供者选择 ============
# "l5" 或 "l3"（"l3" 尚未实现，设为该值服务会在启动时失败，见 L3Provider）
DATA_PROVIDER = os.getenv("DATA_PROVIDER", "l5")

# ============ 任务队列 ============
# running 任务超过该秒数没有心跳更新即视为超时（默认 7200 秒 = 2 小时）
TASK_TIMEOUT_SEC = int(os.getenv("TASK_TIMEOUT_SEC", "7200"))

# ============ 安全 / CORS ============
# DELETE /api/cache/{gene} 的管理员令牌；未设置时该接口一律返回 403。
LMNA_ADMIN_TOKEN = os.getenv("LMNA_ADMIN_TOKEN", "")
# 允许的跨域来源，逗号分隔；为空表示同源部署，不启用 CORS 中间件（D2）。
LMNA_CORS_ORIGINS = os.getenv("LMNA_CORS_ORIGINS", "")


def signature_params() -> dict:
    """当前签名计算所用的可复现参数（L2 会在此基础上加入 ALGO_VERSION）。"""
    return {
        "DATA_PROVIDER": DATA_PROVIDER,
        "KS_THRESHOLD": KS_THRESHOLD,
        "FDR_THRESHOLD": FDR_THRESHOLD,
        "BOOTSTRAP_N": BOOTSTRAP_N,
        "RANDOM_SEED": RANDOM_SEED,
        "FAST_MODE_TOP_N": FAST_MODE_TOP_N,
        "MAX_GENES_PER_DIRECTION": MAX_GENES_PER_DIRECTION,
    }

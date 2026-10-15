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

# 缓存目录
CACHE_DIR = os.path.join(PROJECT_ROOT, "cache")
SIGNATURE_CACHE_DIR = os.path.join(CACHE_DIR, "signatures")
DRUG_SCORE_CACHE_DIR = os.path.join(CACHE_DIR, "drug_scores")
TASK_CACHE_DIR = os.path.join(CACHE_DIR, "tasks")

# 确保缓存目录存在
for d in [SIGNATURE_CACHE_DIR, DRUG_SCORE_CACHE_DIR, TASK_CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

# ============ 签名计算参数 ============
MIN_SH_SAMPLES = 3          # 最少 shRNA 样本数
KS_THRESHOLD = float(os.getenv("KS_THRESHOLD", "0.2"))          # KS score 阈值（绝对值）
FDR_THRESHOLD = float(os.getenv("FDR_THRESHOLD", "0.05"))       # BH 校正后 P 值阈值（L5 建议 0.05，L3 建议 0.001）
BOOTSTRAP_N = int(os.getenv("BOOTSTRAP_N", "1000"))             # Bootstrap 次数（本地测试默认 1000，服务器 L3 建议 100000）
RANDOM_SEED = 42            # 随机种子

# 快速模式：绕过统计显著性，直接取 |KS| 最大的 N 个基因作为 signature（仅用于前后端联调）
# 设置为 0 表示关闭（本地测试默认开启 100，服务器 L3 建议关闭）
FAST_MODE_TOP_N = int(os.getenv("FAST_MODE_TOP_N", "100"))

# ============ 药物筛选参数 ============
DEFAULT_TOP_K = 50
DEFAULT_BOTTOM_K = 50

# ============ API 配置 ============
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8001"))

# ============ 数据提供者选择 ============
# "l5" 或 "l3"
DATA_PROVIDER = os.getenv("DATA_PROVIDER", "l5")

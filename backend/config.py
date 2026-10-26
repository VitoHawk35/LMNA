#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基因敲低签名与药物筛选系统配置
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

# 矩阵维度（L1000 landmark genes × signatures）
# D1（R11）：不再硬编码。优先读 integrity.json 指纹里的 matrix_shape；
# 其次由花名册行数推导并用矩阵文件字节数交叉验证；
# 数据文件不在本机时（如 fixture 测试 / CI）回退到 L1000 名义默认值。
def _resolve_matrix_dims():
    import json as _json

    fp_path = os.path.join(DATA_DIR, "integrity.json")
    if os.path.exists(fp_path):
        try:
            with open(fp_path, "r", encoding="utf-8") as f:
                shape = _json.load(f).get("matrix_shape")
            if shape and len(shape) == 2 and all(int(x) > 0 for x in shape):
                return int(shape[0]), int(shape[1])
        except (OSError, ValueError, TypeError):
            pass  # 指纹损坏时交给启动完整性检查报错，这里继续回退

    def _count_rows(path):
        # 去掉末尾空行后，换行符个数 = 数据行数（首行为表头）
        with open(path, "rb") as f:
            data = f.read().rstrip(b"\r\n")
        if not data:
            return 0
        return data.count(b"\n")

    if all(os.path.exists(p) for p in (MATRIX_PATH, COL_NAMES_PATH, ROW_NAMES_PATH)):
        try:
            n_genes = _count_rows(ROW_NAMES_PATH)
            n_sigs = _count_rows(COL_NAMES_PATH)
            if n_genes > 0 and n_sigs > 0:
                expected = n_genes * n_sigs * 4  # float32 裸 memmap
                if os.path.getsize(MATRIX_PATH) == expected:
                    return n_genes, n_sigs
        except OSError:
            pass

    return 12328, 473647  # L1000 名义默认（数据不在本机时的回退）


N_GENES, N_SIGS = _resolve_matrix_dims()

# 缓存目录（可用 LMNA_CACHE_DIR 覆盖，测试时指向临时目录）
CACHE_DIR = os.getenv("LMNA_CACHE_DIR", os.path.join(PROJECT_ROOT, "cache"))
SIGNATURE_CACHE_DIR = os.path.join(CACHE_DIR, "signatures")
DRUG_SCORE_CACHE_DIR = os.path.join(CACHE_DIR, "drug_scores")
TASK_CACHE_DIR = os.path.join(CACHE_DIR, "tasks")

# 确保缓存目录存在
for d in [SIGNATURE_CACHE_DIR, DRUG_SCORE_CACHE_DIR, TASK_CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

# ============ 签名计算参数 ============
# 算法版本号：签名/打分算法每次发生不兼容变化时 +1。
# 该值参与缓存键（signature_params），旧版本的缓存文件不会被读到。
ALGO_VERSION = "2"

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

# ============ 基因适用性判档（L3，规则 4.4 修订版） ============
# 第一层生物学注释表（D4，🧑‍⚖️ 待用户确认来源与许可）：
# 列 gene, expressed_in_l1000_cells, tissue_specific, receptor_or_channel。
# 文件不存在时判档显示“未知”，不影响档位。
GENE_ANNOTATIONS_PATH = os.getenv(
    "GENE_ANNOTATIONS_PATH", os.path.join(DATA_DIR, "gene_annotations.tsv")
)

# 判档阈值（报告 4.4 修订版；做成环境变量便于后续校准）
SUITABILITY_MIN_HAIRPINS = int(os.getenv("SUITABILITY_MIN_HAIRPINS", "2"))
SUITABILITY_MIN_SIG = int(os.getenv("SUITABILITY_MIN_SIG", "5"))
SUITABILITY_YELLOW_MIN_SIG = int(os.getenv("SUITABILITY_YELLOW_MIN_SIG", "20"))
SUITABILITY_JACCARD_GREEN = float(os.getenv("SUITABILITY_JACCARD_GREEN", "0.5"))
SUITABILITY_JACCARD_RED = float(os.getenv("SUITABILITY_JACCARD_RED", "0.3"))
# 去掉一条 hairpin 后至少剩余的样本数；少于该值则跳过该 hairpin
LOHO_MIN_REMAINING = int(os.getenv("LOHO_MIN_REMAINING", "3"))

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
# "l5"（默认，MODZ 签名级）/ "l3"（L7e：签名走 L3 派生层 + 药物走 L5
# 的 CompositeProvider）/ "fixture"（测试）
DATA_PROVIDER = os.getenv("DATA_PROVIDER", "l5")

# L3 派生层目录（scripts/build_l3_derived.py 的产物；服务器红线目录为
# /home/keji/l3_tmp/derived/l3_v1，最终落盘位置由交付时与用户确认）
L3_DERIVED_DIR = os.getenv(
    "L3_DERIVED_DIR", os.path.join(DATA_DIR, "derived", "l3_v1")
)

# 签名聚合口径（参与缓存键，隔离 L3 实例级与 L5 MODZ 两套缓存文件）
SIGNATURE_AGGREGATION = "instance" if DATA_PROVIDER.strip().lower() == "l3" \
    else "modz"

# ============ 任务队列 ============
# running 任务超过该秒数没有心跳更新即视为超时（默认 7200 秒 = 2 小时）
TASK_TIMEOUT_SEC = int(os.getenv("TASK_TIMEOUT_SEC", "7200"))

# ============ 安全 / CORS ============
# DELETE /api/cache/{gene} 的管理员令牌；未设置时该接口一律返回 403。
LMNA_ADMIN_TOKEN = os.getenv("LMNA_ADMIN_TOKEN", "")
# 允许的跨域来源，逗号分隔；为空表示同源部署，不启用 CORS 中间件（D2）。
LMNA_CORS_ORIGINS = os.getenv("LMNA_CORS_ORIGINS", "")


def signature_params() -> dict:
    """当前签名/药物打分所用的可复现参数，参与缓存键哈希。"""
    return {
        "ALGO_VERSION": ALGO_VERSION,
        "DATA_PROVIDER": DATA_PROVIDER,
        # L7e：聚合口径（instance/modz），与 DATA_PROVIDER 一起隔离
        # L3/L5 签名缓存文件名（含药物缓存——同一哈希同时用于两种缓存）。
        "aggregation": SIGNATURE_AGGREGATION,
        "KS_THRESHOLD": KS_THRESHOLD,
        "FDR_THRESHOLD": FDR_THRESHOLD,
        "BOOTSTRAP_N": BOOTSTRAP_N,
        "RANDOM_SEED": RANDOM_SEED,
        "FAST_MODE_TOP_N": FAST_MODE_TOP_N,
        "MAX_GENES_PER_DIRECTION": MAX_GENES_PER_DIRECTION,
        # L4 起药物 p 值依赖该参数；放进同一缓存键，避免改 N 后读到旧 p 值。
        "DRUG_NULL_N": DRUG_NULL_N,
    }

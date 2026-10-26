#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7e 阶段 1 spike 公共模块：路径、常量、KS/BH/LOHO 工具函数。

口径来源（不得回退的约定）：
- shRNA 实例筛选：pert_type == 'trt_sh' 精确匹配（backend/l5_provider.py:114-117），
  禁止 startswith（会混入 trt_sh.cgs / trt_sh.css 共识签名）。
- 行/列 ID 一律从 gctx 内部 0/META/ROW/id、0/META/COL/id 读取。
- KS 符号约定（backend/signature_engine.py:130-143）：样本内秩 1 = 表达最高，
  KS > 0 = 敲低后上调。
- 显著性阈值与现网 v2 生产一致（~/lmna_v2/start_v2.sh）：
  KS_THRESHOLD=0.2，FDR_THRESHOLD=0.001，BOOTSTRAP_N=100000，RANDOM_SEED=42。
"""

import numpy as np

# ---------------- 服务器路径 ----------------
P1_L3_GCTX = "/data2/wanggang/camp/level3/GSE92742_Broad_LINCS_Level3_INF_mlr12k_n1319138x12328.gctx"
P1_INST_INFO = "/data2/wanggang/camp/level3/GSE92742_Broad_LINCS_inst_info.txt"
GENE_INFO = "/home/keji/cmap_v2_data/GSE92742_Broad_LINCS_gene_info.txt.gz"

# v1 重建的 shRNA z 值（mean/std 口径，analysis/zsvc_build.py 产物）
V1_Z_DAT = "/home/keji/lmna_app/LMNA/cache/_l4zsvc_shrna_z.dat"
V1_Z_META = "/home/keji/lmna_app/LMNA/cache/_l4zsvc_shrna_z.meta.json"

# L5 缓存签名（b031a48b8a = 与现网 v2 相同的参数哈希）
L5_CACHED_SIG_DIR = "/home/keji/lmna_v3_cache/signatures"

OUT_ROOT = "/home/keji/l3_tmp"
OUT_DATA = OUT_ROOT + "/data"
OUT_RESULTS = OUT_ROOT + "/results"

# ---------------- spike 常量 ----------------
GENES = ["CDK4", "MTOR", "EGFR", "TOP2A", "LMNA"]
N_BACKGROUND = 2000          # KS 随机背景池（同一份 L3 数据内抽样）
MIN_CTL_PER_PLATE = 3        # 同板 ctl_vector 下限，低于则回退
EPS_SCALE = 1e-6             # MAD*1.4826 低于此值视为 0 → NaN

KS_THRESHOLD = 0.2
FDR_THRESHOLD = 0.001
BOOTSTRAP_N = 100000
RANDOM_SEED = 42
MAX_GENES_PER_DIRECTION = 50

READ_CHUNK = 20000           # gctx 行读取块大小（与 zsvc_build.py 一致）


# ---------------- KS / BH（逐行复制 backend/signature_engine.py 的数学） ----------------
def ks_uniform_batch(ranks_matrix: np.ndarray, G: int) -> np.ndarray:
    """带符号 KS；KS > 0 = 敲低后上调。ranks_matrix: (G, N)，秩 1 = 表达最高。"""
    N = ranks_matrix.shape[1]
    ranks_sorted = np.sort(ranks_matrix, axis=1)
    i = np.arange(1, N + 1)
    D_plus = np.max(i / N - ranks_sorted / G, axis=1)
    D_minus = np.max(ranks_sorted / G - (i - 1) / N, axis=1)
    scores = np.where(D_plus >= D_minus, D_plus, -D_minus)
    return scores


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    """与 signature_engine._benjamini_hochberg 一致。"""
    n = len(p_values)
    if n == 0:
        return p_values.copy()
    sorted_idx = np.argsort(p_values)
    sorted_p = p_values[sorted_idx]
    bh_values = sorted_p * n / np.arange(1, n + 1)
    bh_values = np.minimum.accumulate(bh_values[::-1])[::-1]
    bh_values = np.clip(bh_values, 0, 1)
    result = np.empty(n, dtype=np.float64)
    result[sorted_idx] = bh_values
    return result


def bootstrap_null_ks_batched(pool_ranks: np.ndarray, n_sample: int, n_boot: int,
                              rng: np.random.Generator, batch: int = 500) -> np.ndarray:
    """
    与 signature_engine._bootstrap_null_ks 分布等价的分块向量化版本：
    每次从池（不含目标基因样本）无放回抽 n_sample 列算带符号 KS。
    仅做批量加速（抽列的随机序列与逐次版不同，但同为 seed 固定的均匀抽样）。
    返回 (n_boot, G)。
    """
    G, N = pool_ranks.shape
    if n_sample > N:
        raise ValueError(f"Bootstrap 池不足：需要 {n_sample}，池 {N}")
    # 内存自适应：单批 G*batch*n_sample 个 int16 控制在 ~400MB 内
    batch = int(max(20, min(batch, 4e8 / (G * max(n_sample, 1) * 2))))
    out = np.empty((n_boot, G), dtype=np.float32)
    i = np.arange(1, n_sample + 1)
    for s in range(0, n_boot, batch):
        b = min(batch, n_boot - s)
        idx = np.stack([rng.choice(N, n_sample, replace=False) for _ in range(b)])
        sub = pool_ranks[:, idx]                    # (G, b, n_sample)
        rs = np.sort(sub, axis=2)
        d_plus = (i / n_sample - rs / G).max(axis=2)    # (G, b)
        d_minus = (rs / G - (i - 1) / n_sample).max(axis=2)
        ks = np.where(d_plus >= d_minus, d_plus, -d_minus)
        out[s:s + b] = ks.T
    return out


def rank_columns(expr: np.ndarray) -> np.ndarray:
    """列内降序排名：1 = 表达最高。NaN 经 argsort 排到末尾（秩最大，视作最低）。"""
    return np.argsort(np.argsort(-expr, axis=0), axis=0).astype(np.int16) + 1


# ---------------- LOHO（逐行复制 backend/suitability.py 的数学） ----------------
def loho_jaccard_min(ranks: np.ndarray, hairpin_ids, full_top_indices, G: int,
                     k: int, min_remaining: int = 3):
    """返回 (min_jaccard 或 None, detail)。"""
    ranks = np.asarray(ranks)
    hairpins = np.asarray([str(h) for h in hairpin_ids])
    k = int(max(1, min(int(k), int(G))))
    full_set = {int(i) for i in full_top_indices}
    if not full_set or ranks.ndim != 2 or ranks.shape[1] != hairpins.shape[0]:
        return None, {"k": k, "n_hairpins": int(len(np.unique(hairpins))),
                      "n_hairpins_used": 0,
                      "n_hairpins_skipped": int(len(np.unique(hairpins)))}
    jaccards, skipped = [], 0
    for hairpin in np.unique(hairpins):
        keep = hairpins != hairpin
        if int(keep.sum()) < min_remaining:
            skipped += 1
            continue
        ks = ks_uniform_batch(ranks[:, keep], G)
        top_set = {int(i) for i in np.argsort(-np.abs(ks))[:k]}
        union = full_set | top_set
        inter = full_set & top_set
        jaccards.append(len(inter) / len(union) if union else 1.0)
    detail = {"k": k, "n_hairpins": int(len(np.unique(hairpins))),
              "n_hairpins_used": len(jaccards), "n_hairpins_skipped": skipped}
    if not jaccards:
        return None, detail
    return float(min(jaccards)), detail


def grade_lite(n_sig: int, loho, target_ks, target_is_landmark: bool,
               n_hairpins: int) -> str:
    """
    suitability.py RULE_VERSION 4.5 的核心判档（不含第一层生物学注释，
    注释缺失时本就不影响档位）：n_sig 阈值 5/20，LOHO 阈值 0.3/0.5，
    D1 防线2（landmark 靶基因自身 KS > 0 时绿降黄）。
    """
    if n_hairpins < 2:
        return "red"
    if n_sig < 5:
        return "red"
    if loho is None or loho < 0.3:
        return "red"
    if n_sig >= 5 and loho >= 0.5:
        if target_is_landmark and target_ks is not None and target_ks > 0:
            return "yellow"
        return "green"
    if n_sig >= 20 and 0.3 <= loho < 0.5:
        return "yellow"
    return "red"

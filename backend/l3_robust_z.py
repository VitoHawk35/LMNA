#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7e · L3 robust z 纯函数模块（口径已拍板，见 docs/design/L7e-spike-report.md §7）

公式（每板 p、每基因 g）：
    med[g]   = median(同板 ctl_vector 的 x[:, g])
    mad[g]   = median(|x_ctl[:, g] − med[g]|)
    raw[g]   = 1.4826 * mad[g]
    floor    = median(raw) * SCALE_FLOOR_REL          # 同板 scale 中位数 × 0.01
    scale[g] = max(raw[g], floor)                     # tiny-MAD 防爆
    z[i, g]  = (x[i, g] − med[g]) / scale[g]

边界口径：
    - raw[g] <= EPS_SCALE（MAD=0 / 量化退化）→ 该基因在该板置 NaN
      （不得进秩签名；rank_columns_nanaware 给 NaN 配哨兵秩 0，
       SignatureEngine 把任何含 NaN 的基因从签名结果中剔除并计数）。
    - 同板 ctl_vector 孔数 < MIN_CTL_PER_PLATE → 回退同细胞系 ctl_vector
      （提取池内聚合，仍 < 下限再回退全局），元数据记 fallback_level
      0=同板 / 1=同细胞系 / 2=全局。

本模块不依赖 h5py / 服务器路径，可脱离 52GB 数据做单测。
"""

import numpy as np

MIN_CTL_PER_PLATE = 3      # 同板 ctl_vector 下限，低于则回退
EPS_SCALE = 1e-6           # 1.4826*MAD 低于此值视为 MAD=0 → NaN
SCALE_FLOOR_REL = 0.01     # scale floor = 同板 scale 中位数 × 此系数
MAD_TO_SD = 1.4826         # 正态一致性常数

# 秩矩阵哨兵：NaN 基因的秩（有效秩从 1 开始，0 可区分）
RANK_NAN_SENTINEL = 0


def plate_robust_stats(control_values: np.ndarray):
    """
    由一组对照孔的表达值计算 robust z 参数。

    Args:
        control_values: (n_controls, G) 数组（n_controls >= 1）

    Returns:
        (median, scale, bad_mask)：均为一维 float64 数组（bad_mask 为 bool）。
        bad_mask[g] = True 表示 MAD≈0，该基因应置 NaN（不参与 scale floor
        替换——floor 只救 tiny-MAD，不救 MAD=0）。
    """
    vals = np.asarray(control_values, dtype=np.float64)
    if vals.ndim != 2 or vals.shape[0] < 1:
        raise ValueError(f"control_values 形状非法: {vals.shape}")
    median = np.median(vals, axis=0)
    mad = np.median(np.abs(vals - median), axis=0)
    raw = MAD_TO_SD * mad
    # floor 用全部基因的 raw scale 中位数（含 0；978 个基因中个别 0 不动中位数）
    floor = float(np.median(raw)) * SCALE_FLOOR_REL
    bad_mask = (~np.isfinite(raw)) | (raw <= EPS_SCALE) | (~np.isfinite(median))
    scale = np.maximum(raw, floor)
    return median, scale, bad_mask


def resolve_control_stats(plate_id: str, cell_id: str, plate_stats: dict,
                          cell_stats: dict, global_stats,
                          min_ctl: int = MIN_CTL_PER_PLATE):
    """
    三级回退选取对照统计量。

    *_stats 的值均为 (median, scale, bad_mask, n_controls)。

    Returns:
        (median, scale, bad_mask, fallback_level)
        fallback_level: 0=同板, 1=同细胞系, 2=全局
    """
    st = plate_stats.get(plate_id)
    if st is not None and st[3] >= min_ctl:
        return st[0], st[1], st[2], 0
    cs = cell_stats.get(cell_id)
    if cs is not None and cs[3] >= min_ctl:
        return cs[0], cs[1], cs[2], 1
    return global_stats[0], global_stats[1], global_stats[2], 2


def apply_robust_z(x: np.ndarray, median: np.ndarray, scale: np.ndarray,
                   bad_mask: np.ndarray) -> np.ndarray:
    """单行/多行表达值 → robust z；bad_mask 处置 NaN。返回新数组。"""
    z = (np.asarray(x, dtype=np.float64) - median) / scale
    z = z.astype(np.float32)
    z[..., bad_mask] = np.nan
    return z


def rank_columns_nanaware(expr: np.ndarray) -> np.ndarray:
    """
    列内降序排名（1 = 表达最高），NaN 不参与排名、配哨兵秩 RANK_NAN_SENTINEL。

    无 NaN 时与 SignatureEngine 现行口径逐元素一致：
        argsort(argsort(-expr, axis=0), axis=0).astype(int16) + 1
    有 NaN 时：有限值占 1..k（k=该列有限值个数），NaN 位置为 0——
    即「NaN 基因被剔除后再排名」，不会挤占最低秩（避免持家基因假性下调）。
    """
    expr = np.asarray(expr)
    ranks = np.argsort(np.argsort(-expr, axis=0), axis=0) + 1
    nan_mask = ~np.isfinite(expr)
    if nan_mask.any():
        # 有效秩从 1 开始，哨兵 0 可区分（不进秩签名）
        ranks[nan_mask] = RANK_NAN_SENTINEL
    return ranks.astype(np.int16)

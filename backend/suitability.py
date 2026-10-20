#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基因适用性判档（task-L3）

规则依据：报告 4.4 修订版（以 LOHO 稳定性为核心，不再使用旧的 13 项打分），
D1 起追加防线2 规则（RULE_VERSION 4.5）：目标基因是 landmark 但敲低后自身
KS > 0（自身未下降）时，最高只给黄档。

档位（依次判断）：
    red    : 独立 hairpin（pert_id 去重）< 2；或算不出签名 / n_sig < 5；
             或 fast_mode_used；或注释判定"不表达 / 组织特异受体或通道"；
             或不满足黄/绿档。
    yellow : n_sig >= 20 且 loho_jaccard_min ∈ [0.3, 0.5)；
             或满足绿档条件但注释提示"组织专有"；
             或满足绿档条件但目标基因自身 KS > 0（D1）。
    green  : n_sig >= 5 且 loho_jaccard_min >= 0.5。

LOHO（leave-one-hairpin-out）Jaccard：
    k = max(10, len(up_genes) + len(down_genes))（封顶后的数量）；
    对每条 hairpin，去掉它的全部样本（剩余 < 3 个则跳过）重算带符号 KS，
    取 |KS| 前 k 个基因，与完整签名的 |KS| 前 k 个基因求 Jaccard；
    取所有 hairpin 的最小值；一条都算不出来则为 None（→ red）。

符号约定（与 L1 一致）：
    样本内秩 1 = 表达最高；KS > 0 = 敲低后上调；KS < 0 = 下调。
    LOHO 只使用 |KS| 排序，不依赖 KS 的符号方向。
"""

import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

import config

RULE_VERSION = "4.5"

# 注释表读取缓存：path -> (mtime, DataFrame)
_ANNOTATION_CACHE: Dict[str, Tuple[float, pd.DataFrame]] = {}


def _parse_bool(value) -> Optional[bool]:
    """把注释表里的布尔写法转成 bool；无法识别时返回 None（未知）。"""
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("true", "t", "1", "yes", "y", "是"):
        return True
    if text in ("false", "f", "0", "no", "n", "否"):
        return False
    return None


def _annotation_path(path: Optional[str] = None) -> str:
    return path or getattr(config, "GENE_ANNOTATIONS_PATH", "")


def load_annotation(
    gene: str,
    path: Optional[str] = None,
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    读取第一层生物学注释（D4，路径可用 GENE_ANNOTATIONS_PATH 配置）。

    Returns:
        (annotation, reason)
        - 文件存在且找到该基因：annotation 为 dict，reason 为 None；
        - 文件不存在 / 读取失败 / 表中无该基因：annotation 为 None，
          reason 是给研究者看的中文说明（判档时显示"未知"，不影响档位）。
    """
    ann_path = _annotation_path(path)
    if not ann_path or not os.path.exists(ann_path):
        return None, (
            "未提供生物学注释（gene_annotations.tsv 未配置），"
            "第一层显示为“未知”，请研究者自行判断"
        )

    try:
        mtime = os.path.getmtime(ann_path)
        cached = _ANNOTATION_CACHE.get(ann_path)
        if cached is not None and cached[0] == mtime:
            df = cached[1]
        else:
            df = pd.read_csv(
                ann_path, sep="\t", dtype=str, keep_default_na=False
            )
            _ANNOTATION_CACHE[ann_path] = (mtime, df)
    except Exception as exc:  # 注释表是可选输入，任何读取问题都降级为"未知"
        return None, (
            f"生物学注释读取失败（{exc}），第一层显示为“未知”，"
            "请研究者自行判断"
        )

    required = {
        "gene",
        "expressed_in_l1000_cells",
        "tissue_specific",
        "receptor_or_channel",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        return None, (
            f"生物学注释表缺少列 {', '.join(missing)}，第一层显示为“未知”，"
            "请研究者自行判断"
        )

    gene_upper = gene.strip().upper()
    match = df[df["gene"].astype(str).str.strip().str.upper() == gene_upper]
    if match.empty:
        return None, (
            f"生物学注释表中没有 {gene_upper}，第一层显示为“未知”，"
            "请研究者自行判断"
        )

    row = match.iloc[0]
    annotation = {
        "gene": gene_upper,
        "expressed_in_l1000_cells": _parse_bool(row["expressed_in_l1000_cells"]),
        "tissue_specific": _parse_bool(row["tissue_specific"]),
        "receptor_or_channel": _parse_bool(row["receptor_or_channel"]),
    }
    return annotation, None


def precheck(provider, gene: str) -> Dict:
    """
    数据前置检查（只读元数据，几秒内可返回）。

    Returns:
        {
            "gene_name": str,
            "n_samples": int,        # trt_sh 样本数
            "n_hairpins": int,       # pert_id 去重后的独立 hairpin 数
            "n_cells": int,          # 细胞系数
            "cell_lines": List[str],
            "data_gate_ok": bool,    # 是否通过数据门槛（hairpin >= 2）
            "reasons": List[str],    # 中文白话
        }
    """
    gene_upper = gene.strip().upper()
    df = provider.get_shrna_samples(gene_upper)
    n_samples = int(len(df))

    if n_samples and "pert_id" in df.columns:
        n_hairpins = int(df["pert_id"].nunique())
    else:
        n_hairpins = 0

    if n_samples and "cell_id" in df.columns:
        cell_lines = sorted(
            str(c) for c in df["cell_id"].dropna().unique().tolist() if str(c)
        )
    else:
        cell_lines = []
    n_cells = len(cell_lines)

    min_hairpins = int(getattr(config, "SUITABILITY_MIN_HAIRPINS", 2))
    reasons: List[str] = []

    if n_samples == 0:
        reasons.append("没有 shRNA 敲低样本，无法计算签名")
        data_gate_ok = False
    elif n_hairpins < min_hairpins:
        reasons.append(
            f"独立 hairpin 只有 {n_hairpins} 个（<{min_hairpins}），"
            "无法排除 shRNA 脱靶"
        )
        data_gate_ok = False
    else:
        data_gate_ok = True
        reasons.append(
            f"数据前置门槛通过：{n_samples} 个样本、{n_hairpins} 个 hairpin、"
            f"{n_cells} 个细胞系"
        )
        if n_samples < 6:
            reasons.append(
                f"样本数偏少（{n_samples} < 6），稳定性可能不足（仅作参考，不单独判红）"
            )

    return {
        "gene_name": gene_upper,
        "n_samples": n_samples,
        "n_hairpins": n_hairpins,
        "n_cells": n_cells,
        "cell_lines": cell_lines,
        "data_gate_ok": data_gate_ok,
        "reasons": reasons,
    }


def loho_jaccard_min(
    ranks: np.ndarray,
    hairpin_ids: Sequence[str],
    full_top_indices: Sequence[int],
    G: int,
    k: Optional[int] = None,
    min_remaining: Optional[int] = None,
) -> Tuple[Optional[float], Dict]:
    """
    计算留一 hairpin 的签名 Jaccard 最小值。

    Args:
        ranks: (G, n_samples) 的样本内秩矩阵（1 = 表达最高）。
        hairpin_ids: 长度 n_samples，与 ranks 的列一一对应。
        full_top_indices: 完整签名 |KS| 前 k 个基因的行下标。
        G: 基因数（KS 的分母）。
        k: 取前 k 个基因；缺省时使用 len(full_top_indices)。
        min_remaining: 去掉一条 hairpin 后至少剩余的样本数，缺省 3。

    Returns:
        (min_jaccard, detail)
        min_jaccard 为 None 表示没有一条 hairpin 能算出结果（→ red）。
    """
    ranks = np.asarray(ranks)
    hairpins = np.asarray([str(h) for h in hairpin_ids])
    if min_remaining is None:
        min_remaining = int(getattr(config, "LOHO_MIN_REMAINING", 3))

    if k is None:
        k = len(full_top_indices)
    k = int(max(1, min(int(k), int(G))))

    full_set = {int(i) for i in full_top_indices}
    if not full_set or ranks.ndim != 2 or ranks.shape[1] != hairpins.shape[0]:
        return None, {
            "k": k,
            "n_hairpins": int(len(np.unique(hairpins))),
            "n_hairpins_used": 0,
            "n_hairpins_skipped": int(len(np.unique(hairpins))),
        }

    # 局部 import 避免 signature_engine <-> suitability 的循环依赖
    from signature_engine import ks_uniform_batch

    jaccards: List[float] = []
    skipped = 0
    for hairpin in np.unique(hairpins):
        keep = hairpins != hairpin
        if int(keep.sum()) < min_remaining:
            skipped += 1
            continue

        sub_ranks = ranks[:, keep]
        ks = ks_uniform_batch(sub_ranks, G)
        top = np.argsort(-np.abs(ks))[:k]
        top_set = {int(i) for i in top}
        union = full_set | top_set
        inter = full_set & top_set
        jaccards.append(len(inter) / len(union) if union else 1.0)

    detail = {
        "k": k,
        "n_hairpins": int(len(np.unique(hairpins))),
        "n_hairpins_used": len(jaccards),
        "n_hairpins_skipped": skipped,
    }
    if not jaccards:
        return None, detail
    return float(min(jaccards)), detail


def grade(
    signature: Dict,
    precheck_result: Dict,
    annotation: Optional[Dict] = None,
    annotation_reason: Optional[str] = None,
) -> Dict:
    """
    根据签名、前置检查与第一层注释判档（红/黄/绿）。

    `signature` 需包含（由 SignatureEngine 写入）：
        n_sig, fast_mode, up_genes, down_genes, ks_scores,
        loho_jaccard_min, target_median_z, loho_detail（可选）。

    Returns:
        {
            "grade": "red" | "yellow" | "green",
            "reasons": List[str],
            "loho_jaccard_min": float | None,
            "n_sig": int,
            "reference": {...},          # 只展示、不判档
            "annotation_used": bool,
            "rule_version": str,
        }
    """
    gene = str(signature.get("gene_name", precheck_result.get("gene_name", "")))
    gene = gene.strip().upper()

    up_genes = list(signature.get("up_genes") or [])
    down_genes = list(signature.get("down_genes") or [])
    n_sig = int(signature.get("n_sig", len(up_genes) + len(down_genes)))
    fast_mode = bool(signature.get("fast_mode", False))
    loho = signature.get("loho_jaccard_min")
    loho = None if loho is None else float(loho)
    loho_detail = signature.get("loho_detail") or {}

    min_sig = int(getattr(config, "SUITABILITY_MIN_SIG", 5))
    yellow_min_sig = int(getattr(config, "SUITABILITY_YELLOW_MIN_SIG", 20))
    jaccard_green = float(getattr(config, "SUITABILITY_JACCARD_GREEN", 0.5))
    jaccard_red = float(getattr(config, "SUITABILITY_JACCARD_RED", 0.3))

    reasons: List[str] = []
    red_hit = False

    # ---- 第一层注释（D4）：缺失只提示，不影响判档 ----
    tissue_specific: Optional[bool] = None
    if annotation is None:
        reasons.append(
            annotation_reason
            or "未提供生物学注释，第一层显示为“未知”，请研究者自行判断"
        )
    else:
        expressed = annotation.get("expressed_in_l1000_cells")
        tissue_specific = annotation.get("tissue_specific")
        receptor_or_channel = annotation.get("receptor_or_channel")

        if expressed is False:
            red_hit = True
            reasons.append("注释显示靶基因在 L1000 细胞系中不表达")
        elif expressed is True:
            reasons.append("注释显示靶基因在 L1000 细胞系中有表达")
        else:
            reasons.append("注释中“是否在 L1000 细胞系表达”为未知")

        if receptor_or_channel is True and tissue_specific is True:
            red_hit = True
            reasons.append("注释显示靶基因为组织特异的膜受体/离子通道")
        elif receptor_or_channel is True:
            reasons.append("注释显示靶基因为受体/通道（未提示组织特异）")
        elif tissue_specific is True:
            reasons.append("注释提示靶基因组织专有（绿档将降为黄档）")
        elif tissue_specific is False:
            reasons.append("注释显示靶基因非组织专有")

    # ---- 数据前置门槛 ----
    if not precheck_result.get("data_gate_ok", False):
        red_hit = True
        detail = "；".join(precheck_result.get("reasons") or [])
        reasons.append(f"数据前置门槛未通过：{detail}" if detail else "数据前置门槛未通过")

    # ---- 签名质量 ----
    if n_sig < min_sig:
        red_hit = True
        reasons.append(f"显著基因数 n_sig={n_sig} < {min_sig}，签名不可靠")

    if fast_mode:
        red_hit = True
        reasons.append(
            "使用了快速模式（无显著基因时硬取 |KS| 最大的基因），"
            "实测接近随机，不能用于判药"
        )

    if loho is None:
        red_hit = True
        reasons.append("无法计算留一 hairpin 稳定性（LOHO Jaccard 为空）")
    elif loho < jaccard_red:
        red_hit = True
        reasons.append(
            f"留一 hairpin 稳定性 Jaccard={loho:.3f} < {jaccard_red:g}，"
            "签名随 hairpin 变化大"
        )

    green_core = loho is not None and n_sig >= min_sig and loho >= jaccard_green
    yellow_core = (
        loho is not None
        and n_sig >= yellow_min_sig
        and jaccard_red <= loho < jaccard_green
    )

    # ---- D1 防线2：目标基因自身 KS（判档前先行计算，供规则与参考信息共用）----
    ks_scores = signature.get("ks_scores") or {}
    target_is_landmark = gene in ks_scores
    target_ks = None
    if target_is_landmark:
        try:
            target_ks = float(ks_scores[gene])
        except (TypeError, ValueError):
            target_ks = None

    if red_hit:
        grade_value = "red"
        reasons.append(
            "判定为红档：不给药物列表，建议改用“上传患者 / iPSC 差异表达”流程"
        )
    elif green_core and tissue_specific is True:
        grade_value = "yellow"
        reasons.append(
            "满足绿档的稳定性条件，但注释提示组织专有，降为黄档；"
            "建议补充患者组织或 iPSC 数据后再做湿实验"
        )
    elif green_core:
        grade_value = "green"
        reasons.append(
            "判定为绿档：签名稳定（n_sig >= 5 且 LOHO Jaccard >= 0.5）"
        )
    elif yellow_core:
        grade_value = "yellow"
        reasons.append(
            f"判定为黄档：n_sig={n_sig} >= {yellow_min_sig} 且 "
            f"LOHO Jaccard={loho:.3f} 在 [{jaccard_red:g}, {jaccard_green:g}) 区间；"
            "照常给出药物列表，但建议再补一种证据"
        )
    else:
        grade_value = "red"
        reasons.append(
            f"未满足绿档（n_sig >= {min_sig} 且 Jaccard >= {jaccard_green:g}）"
            f"或黄档（n_sig >= {yellow_min_sig} 且 Jaccard 在 "
            f"[{jaccard_red:g}, {jaccard_green:g})）条件"
        )

    # ---- D1 防线2：landmark 靶基因敲低后自身未下降 → 最高黄档 ----
    if (
        grade_value == "green"
        and target_is_landmark
        and target_ks is not None
        and target_ks > 0
    ):
        grade_value = "yellow"
        reasons.append(
            "敲低后目标基因自身未下降（自身 KS > 0），"
            "敲低可能未生效或数据有误，最高只给黄档"
        )

    # ---- 参考信息：只展示，不参与判档 ----
    target_median_z = signature.get("target_median_z")
    if not target_is_landmark:
        target_median_z = None
    elif target_median_z is not None:
        target_median_z = float(target_median_z)

    reference = {
        "n_cells": precheck_result.get("n_cells"),
        "cell_lines": list(precheck_result.get("cell_lines") or []),
        "n_hairpins": precheck_result.get("n_hairpins"),
        "n_samples": precheck_result.get("n_samples"),
        "target_is_landmark": bool(target_is_landmark),
        "target_ks": target_ks,
        "target_median_z": target_median_z,
        "loho_k": loho_detail.get("k"),
        "loho_hairpins_used": loho_detail.get("n_hairpins_used"),
        "loho_hairpins_skipped": loho_detail.get("n_hairpins_skipped"),
    }

    return {
        "grade": grade_value,
        "reasons": reasons,
        "loho_jaccard_min": loho,
        "n_sig": n_sig,
        "reference": reference,
        "annotation_used": annotation is not None,
        "rule_version": RULE_VERSION,
    }

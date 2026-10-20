#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
D1 防线2 · 生物学自检（哨兵基因）。

服务启动后在后台对 3 个哨兵基因（默认 CDK4、PCNA、MYC，可用
LINCS_SENTINEL_GENES 覆盖，逗号分隔）计算敲低签名中"目标基因自身"的
带符号 KS：敲低生效时目标基因应下调，即自身 KS 明显为负（< -0.3）。
行/列错位时该检查会失败——这是防线1被关闭（LINCS_INTEGRITY_MODE=off）
或数据以其他方式损坏时的第二道防线。

判定：被检查的哨兵中 2/3 以上不通过 → /api/health 返回 integrity=suspect，
前端顶部显示黄色横幅"数据自检未通过，结果可能不可靠"。

自检只读数据、只算目标基因一行的 KS（不做 bootstrap），开销可忽略。
"""

import os
import threading
import time
from typing import Dict, List, Optional

import numpy as np

# 哨兵基因默认值：均为 landmark 且在 L1000 中 hairpin 数充足
DEFAULT_SENTINELS = ("CDK4", "PCNA", "MYC")
# 目标基因自身 KS 阈值：敲低生效时应 < -0.3
SELF_KS_THRESHOLD = float(os.getenv("LINCS_SELF_KS_THRESHOLD", "-0.3"))
# 哨兵入选条件：独立 hairpin 数不低于该值
MIN_SENTINEL_HAIRPINS = int(os.getenv("LINCS_SENTINEL_MIN_HAIRPINS", "3"))
# 不通过比例达到 2/3 即判 suspect
SUSPECT_RATIO = 2.0 / 3.0

# 模块级状态（单进程单例；测试可直接读写）
STATE: Dict = {
    "status": "unknown",   # unknown | running | ok | suspect
    "started_at": None,
    "finished_at": None,
    "results": [],
}


def sentinel_genes() -> List[str]:
    raw = os.getenv("LINCS_SENTINEL_GENES", "")
    if raw.strip():
        genes = [g.strip().upper() for g in raw.split(",") if g.strip()]
    else:
        genes = list(DEFAULT_SENTINELS)
    return genes


def compute_self_ks(provider, gene_name: str,
                    min_hairpins: int = MIN_SENTINEL_HAIRPINS) -> Optional[float]:
    """计算某基因敲低签名中目标基因自身的带符号 KS。

    Returns:
        float：目标基因是 landmark 且样本/hairpin 足够时的自身 KS；
        None ：基因无 shRNA 数据、hairpin 不足或不是 landmark（该哨兵跳过）。
    """
    from signature_engine import ks_uniform_batch  # 局部 import 避免循环依赖

    gene_upper = gene_name.strip().upper()
    df = provider.get_shrna_samples(gene_upper)
    if len(df) == 0:
        return None
    if "pert_id" in df.columns and int(df["pert_id"].nunique()) < min_hairpins:
        return None

    symbols = [str(s).strip().upper() for s in provider.get_gene_symbols()]
    if gene_upper not in symbols:
        return None  # 非 landmark，无法算自身 KS
    target_row = symbols.index(gene_upper)

    expr = provider.get_expression_matrix(df["sig_id"].astype(str).tolist())
    if expr.ndim != 2 or expr.shape[1] == 0:
        return None
    # 样本内秩 1 = 表达最高（与 signature_engine 一致）
    ranks = np.argsort(np.argsort(-expr, axis=0), axis=0).astype(np.int16) + 1
    ks = ks_uniform_batch(ranks, expr.shape[0])
    return float(ks[target_row])


def run_self_check(provider, genes: Optional[List[str]] = None) -> Dict:
    """同步执行哨兵自检，返回并记录结果（可被测试直接调用）。"""
    genes = genes or sentinel_genes()
    STATE["status"] = "running"
    STATE["started_at"] = time.time()

    results: List[Dict] = []
    for gene in genes:
        entry = {"gene": gene, "checked": False, "self_ks": None,
                 "pass": None, "note": ""}
        try:
            ks = compute_self_ks(provider, gene)
        except Exception as exc:  # 单个哨兵失败不拖垮自检
            entry["note"] = "计算失败: %s" % exc
            results.append(entry)
            continue
        if ks is None:
            entry["note"] = "无数据 / hairpin 不足 / 非 landmark，跳过"
        else:
            entry["checked"] = True
            entry["self_ks"] = ks
            entry["pass"] = bool(ks < SELF_KS_THRESHOLD)
        results.append(entry)

    checked = [r for r in results if r["checked"]]
    failed = [r for r in checked if not r["pass"]]
    if not checked:
        status = "unknown"
    elif len(failed) / float(len(checked)) >= SUSPECT_RATIO:
        status = "suspect"
    else:
        status = "ok"

    STATE["status"] = status
    STATE["finished_at"] = time.time()
    STATE["results"] = results
    return {
        "status": status,
        "n_checked": len(checked),
        "n_failed": len(failed),
        "results": results,
    }


def start_background_self_check(provider,
                                genes: Optional[List[str]] = None) -> threading.Thread:
    """在后台线程执行自检（不阻塞服务启动）。"""
    thread = threading.Thread(
        target=run_self_check,
        args=(provider, genes),
        name="lincs-integrity-selfcheck",
        daemon=True,
    )
    thread.start()
    return thread


def current_integrity_status() -> str:
    """/api/health 使用：unknown | running | ok | suspect。"""
    return str(STATE.get("status", "unknown"))


def current_integrity_detail() -> Dict:
    """自检明细（哨兵逐个结果），供健康检查或调试接口展示。"""
    return {
        "status": current_integrity_status(),
        "results": list(STATE.get("results") or []),
    }

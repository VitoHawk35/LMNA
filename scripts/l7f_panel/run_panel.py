#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7f 阶段1 · 面板驱动：≥20 靶点 × (签名 + 药物打分 + AUROC + 判档四元组)

模式复用 scripts/l3_exp1_accuracy.py（真实后端 provider_factory →
SignatureEngine → DrugScorer；金标准别名组 pert_iname 小写精确匹配；
AUROC 用 mimic 分方向；签名落盘缓存文件名带 signature_params 短哈希，
换参数/换数据源自动隔离）。靶点与金标准来自 scripts/l7f_panel/panel_def.py。

分片并行：--shard i/n 对排序靶点列表取索引 % n == i 的子集，每分片独立
JSON 与日志，分析脚本（analyze_results.py）合并。阴性对照（20 随机签名
药物 FDR + 判档全红检查）只在 --with-neg-ctrl 的分片跑，每侧跑一次即可。

用法（服务器，红线：只写 /home/keji/l3_tmp/）：
    PY=~/miniconda3/envs/cmap/bin/python
    cd <worktree 检出>
    # L3 侧（4 分片并行示例）
    for i in 0 1 2 3; do
      DATA_PROVIDER=l3 L3_DERIVED_DIR=/home/keji/l3_tmp/derived/l3_v1 \
      CMAP_DATA_DIR=/home/keji/cmap_v2_data LMNA_CACHE_DIR=/home/keji/l3_tmp/l7f_cache \
      BOOTSTRAP_N=100000 FDR_THRESHOLD=0.001 KS_THRESHOLD=0.2 DRUG_NULL_N=10000 \
      LINCS_INTEGRITY_MODE=off FAST_MODE_TOP_N=0 \
      nohup $PY -B scripts/l7f_panel/run_panel.py --side l3 --shard $i/4 \
        $( [ $i -eq 0 ] && echo --with-neg-ctrl ) \
        --out /home/keji/l3_tmp/l7f_results/panel_l3_shard$i.json \
        > /home/keji/l3_tmp/l7f_results/panel_l3_shard$i.log 2>&1 &
    done
    # L5 侧：DATA_PROVIDER=l5，LMNA_CACHE_DIR=/home/keji/l3_tmp/l7f_cache_l5，
    #        输出 panel_l5_shard*.json

产物 JSON：per-target 四元组（n_sig/LOHO/AUROC/判档）+ 金标准名次 +
FDR 统计 + 阴性对照 + 运行参数（signature_params / 判档阈值 / RULE_VERSION）。
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "..", "backend"))
for p in (_HERE, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from panel_def import PANEL, TARGETS  # noqa: E402

t0 = time.time()


def log(msg):
    print(f"[{time.time()-t0:8.1f}s] {msg}", flush=True)


NEG_CTRL_N = 20          # 随机签名数（与 exp1 口径一致）
NEG_UP, NEG_DOWN = 50, 50
NEG_SEED = 42
NEG_NULL_M = 10000       # 与生产 DRUG_NULL_N 一致


def auroc(scores: np.ndarray, pos_mask: np.ndarray):
    """Mann-Whitney AUROC（平均秩处理并列）。正例不足返回 None。

    方向约定（exp1 口径）：scores 为 mimic 分（高 = 药物模拟敲低），
    金标准抑制剂应落在 mimic 高端。
    """
    n_pos = int(pos_mask.sum())
    n_neg = int(len(scores) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return None
    r = pd.Series(scores).rank(method="average").to_numpy()
    return float((r[pos_mask].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def gold_mask(drug_names, target):
    """返回 (pos_mask, found_groups, missing_groups)。别名组小写精确匹配。"""
    lower = [str(n).strip().lower() for n in drug_names]
    pos = np.zeros(len(lower), dtype=bool)
    found, missing = [], []
    for group in PANEL[target]["gold"]:
        hits = [v for v in group if v in lower]
        if hits:
            found.append(sorted(group)[0])
            for v in hits:
                pos[lower.index(v)] = True
        else:
            missing.append(sorted(group)[0])
    return pos, found, missing


def negative_control(engine, scorer, drug_names):
    """20 个随机签名（50 up + 50 down，seed 42）：
    (a) fdr_reversal<0.05 药物比例应 <1%（exp1 口径，null 矩阵缓存等价）；
    (b) 判档阴性对照：随机签名无 hairpin 结构 → LOHO=None → 必须全红。
    """
    from suitability import grade, RULE_VERSION

    D = scorer._drug_matrix
    G, M = D.shape[0], NEG_NULL_M
    n_drugs = len(drug_names)
    rng = np.random.default_rng(NEG_SEED)
    batch = 500
    null = np.empty((M, n_drugs), dtype=np.float32)
    done = 0
    while done < M:
        b = min(batch, M - done)
        keys = rng.random((b, G))
        chosen = np.argpartition(keys, NEG_UP + NEG_DOWN - 1, axis=1)[:, :NEG_UP + NEG_DOWN]
        W = np.zeros((b, G), dtype=np.float32)
        W[np.repeat(np.arange(b), NEG_UP), chosen[:, :NEG_UP].ravel()] = 1.0
        W[np.repeat(np.arange(b), NEG_DOWN), chosen[:, NEG_UP:].ravel()] = -1.0
        null[done:done + b] = np.asarray(W @ D, dtype=np.float32)
        done += b
    log("阴性对照 null 矩阵完成，跑 20 个随机签名 ...")

    symbols = [str(s) for s in engine._shrna_gene_symbols]
    fracs, grades = [], []
    rng_sig = np.random.default_rng(NEG_SEED + 1)
    for k in range(NEG_CTRL_N):
        idx = rng_sig.choice(G, NEG_UP + NEG_DOWN, replace=False)
        up_idx, down_idx = idx[:NEG_UP], idx[NEG_UP:]
        obs = (np.asarray(D[up_idx].sum(axis=0), dtype=np.float64)
               - np.asarray(D[down_idx].sum(axis=0), dtype=np.float64))
        p_rev = (np.count_nonzero(null <= obs.astype(np.float32), axis=0) + 1.0) / (M + 1)
        fdr_rev = engine._benjamini_hochberg(p_rev)
        fracs.append(float((fdr_rev < 0.05).mean()))
        # (b) 判档：随机签名走真实 grade()，无 hairpin → LOHO=None
        sig = {
            "gene_name": f"RANDOM{k}",
            "n_sig": NEG_UP + NEG_DOWN,
            "up_genes": [symbols[i] for i in up_idx],
            "down_genes": [symbols[i] for i in down_idx],
            "ks_scores": {},
            "loho_jaccard_min": None,
            "fast_mode": False,
        }
        pre = {"gene_name": f"RANDOM{k}", "data_gate_ok": True}
        grades.append(grade(sig, pre, annotation=None,
                            annotation_reason="（阴性对照：无注释）")["grade"])

    return {
        "n_random_signatures": NEG_CTRL_N,
        "sig_size": [NEG_UP, NEG_DOWN],
        "null_M": M,
        "seed": NEG_SEED,
        "frac_drugs_fdr_lt_0.05_per_sig": fracs,
        "max_frac": max(fracs),
        "mean_frac": float(np.mean(fracs)),
        "pass_lt_1pct": bool(max(fracs) < 0.01),
        "grades_current_rule": grades,
        "all_red": bool(all(g == "red" for g in grades)),
        "rule_version": RULE_VERSION,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", required=True, choices=["l3", "l5"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard", default="0/1",
                    help="形如 i/n：排序靶点列表取 idx%%n==i 的子集")
    ap.add_argument("--targets", default="",
                    help="逗号分隔靶点子集（覆盖 --shard）")
    ap.add_argument("--with-neg-ctrl", action="store_true",
                    help="本进程附带跑 20 随机签名阴性对照（每侧一次即可）")
    args = ap.parse_args()

    shard_i, shard_n = (int(x) for x in args.shard.split("/"))
    assert 0 <= shard_i < shard_n, f"非法分片 {args.shard}"

    import config
    from provider_factory import create_provider
    from signature_engine import SignatureEngine
    from drug_scorer import DrugScorer
    from cache_manager import signature_params_hash
    import suitability

    assert config.DATA_PROVIDER == args.side, (
        f"DATA_PROVIDER={config.DATA_PROVIDER} 与 --side {args.side} 不一致")

    if args.targets:
        targets = [t.strip().upper() for t in args.targets.split(",") if t.strip()]
        unknown = [t for t in targets if t not in PANEL]
        assert not unknown, f"面板外靶点: {unknown}"
    else:
        targets = [t for i, t in enumerate(TARGETS) if i % shard_n == shard_i]
    log(f"本进程靶点（{len(targets)}）: {','.join(targets)}")

    log(f"构建 provider（{args.side}）...")
    provider = create_provider()
    engine = SignatureEngine(provider)
    scorer = DrugScorer(provider)
    drug_names = [str(n) for n in scorer._drug_names]
    n_drugs = len(drug_names)
    log(f"药物矩阵 {scorer._drug_matrix.shape}，{n_drugs} 种药物")

    # 靶点数据覆盖核实（shRNA 实例数；pert_id 去重 hairpin 数）
    coverage = {}
    for t in targets:
        df = provider.get_shrna_samples(t)
        coverage[t] = {
            "n_samples": int(len(df)),
            "n_hairpins": int(df["pert_id"].nunique()) if len(df) else 0,
            "in_available_genes": bool(t in set(provider.list_available_genes())),
        }
    log(f"覆盖核实: {json.dumps(coverage, ensure_ascii=False)}")

    out = {
        "side": args.side,
        "shard": args.shard,
        "params": config.signature_params(),
        "grading_thresholds": {
            "RULE_VERSION": suitability.RULE_VERSION,
            "SUITABILITY_MIN_SIG": config.SUITABILITY_MIN_SIG,
            "SUITABILITY_YELLOW_MIN_SIG": config.SUITABILITY_YELLOW_MIN_SIG,
            "SUITABILITY_JACCARD_GREEN": config.SUITABILITY_JACCARD_GREEN,
            "SUITABILITY_JACCARD_RED": config.SUITABILITY_JACCARD_RED,
        },
        "n_drugs": n_drugs,
        "coverage": coverage,
        "targets": {},
        "negative_control": {},
    }

    # ---- 面板靶点：签名（落盘缓存）+ 药物打分 + 自身 AUROC ----
    sig_cache_dir = os.path.join(
        os.path.dirname(os.path.abspath(args.out)), f"signatures_{args.side}")
    os.makedirs(sig_cache_dir, exist_ok=True)
    sig_params_hash = signature_params_hash()
    log(f"签名缓存目录 {sig_cache_dir}（参数哈希 {sig_params_hash}）")

    for target in targets:
        sig_cache = os.path.join(
            sig_cache_dir, f"{target}.{sig_params_hash}.json")
        if os.path.exists(sig_cache):
            with open(sig_cache, encoding="utf-8") as fp:
                sig = json.load(fp)
            log(f"[{target}] 签名来自缓存")
        else:
            log(f"[{target}] 计算签名 ...")
            sig = engine.compute_signature(target)
            tmp = sig_cache + f".tmp.{os.getpid()}"
            with open(tmp, "w", encoding="utf-8") as fp:
                json.dump(sig, fp, ensure_ascii=False)
            os.replace(tmp, sig_cache)
        log(f"[{target}] n={sig['n_samples']} n_sig={sig['n_sig']} "
            f"LOHO={sig['loho_jaccard_min']} grade={sig['qc']['grade']} "
            f"excluded_nan={sig.get('n_excluded_nan_genes', 0)}；药物打分 ...")

        res = scorer.score_drugs(sig, method="xsum")
        df = pd.DataFrame(res["all_scores"]).set_index("drug_name")
        # all_scores 按 score 降序，与 drug_names 矩阵列序不同序；
        # 金标准掩码必须按 df.index 构建（exp1 修正口径）。
        mimic = pd.Series(-df["score"].to_numpy(), index=df.index)

        pos, found, missing = gold_mask(list(df.index), target)
        self_auroc = auroc(mimic.to_numpy(), pos)
        rank_desc = mimic.rank(method="min", ascending=False).to_numpy()
        gold_ranks = sorted(int(r) for r in rank_desc[pos])
        out["targets"][target] = {
            "n_samples": int(sig["n_samples"]),
            "n_hairpins": int(sig["n_hairpins"]),
            "n_cells": int(sig["n_cells"]),
            "n_sig": int(sig["n_sig"]),
            "n_up": len(sig["up_genes"]),
            "n_down": len(sig["down_genes"]),
            "loho_jaccard_min": sig["loho_jaccard_min"],
            "grade": sig["qc"]["grade"],
            "rule_version": sig["qc"].get("rule_version"),
            "n_excluded_nan_genes": sig.get("n_excluded_nan_genes", 0),
            "target_median_z": sig["target_median_z"],
            "auroc_self": self_auroc,
            "gold_found": found,
            "gold_missing": missing,
            "gold_best_rank": gold_ranks[0] if gold_ranks else None,
            "gold_ranks": gold_ranks,
            "gold_top50_hits": int(sum(1 for r in gold_ranks if r <= 50)),
            "frac_drugs_fdr_reversal_lt_0.05": float(
                (df["fdr_reversal"] < 0.05).mean()),
        }
        log(f"[{target}] AUROC(自身抑制剂)={self_auroc} "
            f"gold {len(found)}/{len(found)+len(missing)} 在场")

    # ---- 阴性对照（仅 --with-neg-ctrl 分片） ----
    if args.with_neg_ctrl:
        log("阴性对照 ...")
        out["negative_control"] = negative_control(engine, scorer, drug_names)
        nc = out["negative_control"]
        log(f"阴性对照：药物FDR max={nc['max_frac']:.4%} "
            f"判档全红={nc['all_red']}")

    out["elapsed_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    tmp_out = args.out + f".tmp.{os.getpid()}"
    with open(tmp_out, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    os.replace(tmp_out, args.out)
    log(f"写出 {args.out}")


if __name__ == "__main__":
    main()

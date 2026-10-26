#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7e 阶段 2 · 任务 7/8：准确性实验（exp1 口径，服务器只读跑数据，写 l3_tmp）

4 靶点（CDK4/EGFR/MTOR/BRAF）× 2 数据源（L3 派生层 / L5 MODZ）：
- 用真实后端（provider_factory → SignatureEngine → DrugScorer）算签名与药物分；
- 自身抑制剂 AUROC（金标准表 = round2/verification/多基因测试-权威基准.md，
  Drug Repurposing Hub MoA 口径；别名组精确匹配 pert_iname 小写）；
- 交叉对照 4×4：靶点 i 签名下靶点 j 抑制剂集合的 AUROC；
- 20 次随机签名阴性对照（50 up + 50 down，seed 42）：fdr_reversal<0.05
  的药物比例应 <1%。null 矩阵按 (n_up,n_down,M,seed) 缓存——与
  DrugScorer.drug_null 同 seed 同尺寸时抽样序列逐位相同，缓存等价于
  重复调用，只是省去 20 次重复抽样。

用法（服务器，两进程可并行）：
    cd /home/keji/l3_tmp/stage2
    PY=~/miniconda3/envs/cmap/bin/python
    # L3 侧
    DATA_PROVIDER=l3 L3_DERIVED_DIR=/home/keji/l3_tmp/derived/l3_v1 \
    CMAP_DATA_DIR=/home/keji/cmap_v2_data LMNA_CACHE_DIR=/home/keji/l3_tmp/l3cache \
    BOOTSTRAP_N=100000 FDR_THRESHOLD=0.001 KS_THRESHOLD=0.2 DRUG_NULL_N=10000 \
    LINCS_INTEGRITY_MODE=off FAST_MODE_TOP_N=0 \
    $PY -B scripts/l3_exp1_accuracy.py --side l3 --out results/exp1_l3.json
    # L5 侧（同上，DATA_PROVIDER=l5，LMNA_CACHE_DIR=.../l5cache2）

判档阈值建议所需数据（n_sig / LOHO / grade / AUROC / 阴性对照）全部入 JSON。
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(os.path.dirname(_HERE), "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

t0 = time.time()


def log(msg):
    print(f"[{time.time()-t0:8.1f}s] {msg}", flush=True)


TARGETS = ["CDK4", "EGFR", "MTOR", "BRAF"]

# 金标准抑制剂（别名组；组内任一变体命中即算该药在场）
GOLD = {
    "CDK4": [
        {"palbociclib"}, {"ribociclib"}, {"abemaciclib"}, {"dinaciclib"},
        {"alvocidib", "flavopiridol"}, {"roscovitine"},
    ],
    "EGFR": [
        {"gefitinib"}, {"erlotinib"}, {"afatinib"}, {"dacomitinib"},
        {"lapatinib"}, {"canertinib"}, {"pelitinib"},
    ],
    "MTOR": [
        {"sirolimus", "rapamycin"}, {"everolimus"}, {"temsirolimus"},
        {"torin-1", "torin1"}, {"torin-2", "torin2"}, {"azd8055"},
        {"dactolisib", "bez235", "nvp-bez235"}, {"pi-103", "pi103"},
        {"wortmannin"}, {"ly294002"},
    ],
    "BRAF": [
        {"vemurafenib"}, {"dabrafenib"}, {"sorafenib"},
        {"plx-4720", "plx4720"}, {"trametinib"}, {"selumetinib"},
        {"pd-0325901", "pd0325901"}, {"ci-1040", "ci1040"},
    ],
}

NEG_CTRL_N = 20          # 随机签名数
NEG_UP, NEG_DOWN = 50, 50
NEG_SEED = 42
NEG_NULL_M = 10000       # 随机签名 null 大小（与生产 DRUG_NULL_N 一致）


def auroc(scores: np.ndarray, pos_mask: np.ndarray):
    """Mann-Whitney AUROC（平均秩处理并列）。正例不足返回 None。

    方向约定（exp1 口径）：scores 为 mimic 分（mimic = Σz(up) − Σz(down)，
    高 = 药物模拟敲低）。金标准抑制剂药理上模拟敲低，应落在 mimic 高端
    （核验锚点 CDK4 AUROC 0.844→0.964 即此方向；reversal 分方向会读出
    1 − AUROC 的镜像值）。产品对外的"逆转"排序不受影响（那是另一条腿）。
    """
    n_pos = int(pos_mask.sum())
    n_neg = int(len(scores) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return None
    r = pd.Series(scores).rank(method="average").to_numpy()
    return float((r[pos_mask].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def gold_mask(drug_names, target):
    """返回 (pos_mask, found_groups, missing_groups)。"""
    lower = [str(n).strip().lower() for n in drug_names]
    pos = np.zeros(len(lower), dtype=bool)
    found, missing = [], []
    for group in GOLD[target]:
        hits = [v for v in group if v in lower]
        if hits:
            found.append(sorted(group)[0])
            for v in hits:
                pos[lower.index(v)] = True
        else:
            missing.append(sorted(group)[0])
    return pos, found, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", required=True, choices=["l3", "l5"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import config
    from provider_factory import create_provider
    from signature_engine import SignatureEngine
    from drug_scorer import DrugScorer

    assert config.DATA_PROVIDER == args.side, (
        f"DATA_PROVIDER={config.DATA_PROVIDER} 与 --side {args.side} 不一致")

    log(f"构建 provider（{args.side}）...")
    provider = create_provider()
    engine = SignatureEngine(provider)
    scorer = DrugScorer(provider)
    drug_names = [str(n) for n in scorer._drug_names]
    D = scorer._drug_matrix
    n_drugs = len(drug_names)
    log(f"药物矩阵 {D.shape}，{n_drugs} 种药物")

    out = {
        "side": args.side,
        "params": config.signature_params(),
        "n_drugs": n_drugs,
        "targets": {},
        "cross_auroc": {},
        "negative_control": {},
    }

    # ---- 4 靶点：签名 + 药物打分 + 自身 AUROC ----
    per_sig_mimic = {}      # target -> mimic 分（高=模拟敲低，AUROC 用它）
    per_sig_df = {}
    for target in TARGETS:
        log(f"[{target}] 计算签名 ...")
        sig = engine.compute_signature(target)
        log(f"[{target}] n={sig['n_samples']} n_sig={sig['n_sig']} "
            f"LOHO={sig['loho_jaccard_min']} grade={sig['qc']['grade']} "
            f"excluded_nan={sig.get('n_excluded_nan_genes', 0)}；药物打分 ...")
        res = scorer.score_drugs(sig, method="xsum")
        df = pd.DataFrame(res["all_scores"]).set_index("drug_name")
        per_sig_df[target] = df
        mimic = -df["score"].to_numpy()      # score=-mimic → 取负
        per_sig_mimic[target] = mimic

        pos, found, missing = gold_mask(drug_names, target)
        self_auroc = auroc(mimic, pos)
        # 金标准药物名次（按 mimic 分降序）
        rank_desc = pd.Series(mimic).rank(
            method="min", ascending=False).to_numpy()
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
            "excluded_nan_genes": sig.get("excluded_nan_genes", []),
            "target_median_z": sig["target_median_z"],
            "auroc_self": self_auroc,
            "gold_found": found,
            "gold_missing": missing,
            "gold_best_rank": gold_ranks[0] if gold_ranks else None,
            "gold_ranks": gold_ranks,
            "gold_top50_hits": int(sum(1 for r in gold_ranks if r <= 50)),
            "n_drugs_fdr_reversal_lt_0.05": int(
                (df["fdr_reversal"] < 0.05).sum()),
            "frac_drugs_fdr_reversal_lt_0.05": float(
                (df["fdr_reversal"] < 0.05).mean()),
            "top10_reversal": df.sort_values(
                ["fdr_reversal", "score"],
                ascending=[True, False]).head(10).index.tolist(),
        }
        log(f"[{target}] AUROC(自身抑制剂)={self_auroc} "
            f"gold {len(found)}/{len(found)+len(missing)} 在场")

    # ---- 交叉对照 4×4（mimic 分方向） ----
    log("交叉对照 4×4 ...")
    for sig_target in TARGETS:
        row = {}
        for inh_target in TARGETS:
            pos, _, _ = gold_mask(drug_names, inh_target)
            row[inh_target] = auroc(per_sig_mimic[sig_target], pos)
        out["cross_auroc"][sig_target] = row
    # 特异性差值 = 自身 AUROC − 其他靶点抑制剂 AUROC 均值
    for t in TARGETS:
        others = [out["cross_auroc"][t][o] for o in TARGETS if o != t]
        others = [v for v in others if v is not None]
        out["targets"][t]["specificity_delta"] = (
            None if out["targets"][t]["auroc_self"] is None or not others
            else out["targets"][t]["auroc_self"] - float(np.mean(others))
        )

    # ---- 20 次随机签名阴性对照（null 矩阵缓存，等价于 20 次 drug_null） ----
    log(f"阴性对照：{NEG_CTRL_N} 个随机签名（{NEG_UP}+{NEG_DOWN}）...")
    G, M = D.shape[0], NEG_NULL_M
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
    log("null 矩阵完成，跑 20 个随机签名 ...")
    fracs = []
    rng_sig = np.random.default_rng(NEG_SEED + 1)
    for k in range(NEG_CTRL_N):
        idx = rng_sig.choice(G, NEG_UP + NEG_DOWN, replace=False)
        up_idx, down_idx = idx[:NEG_UP], idx[NEG_UP:]
        obs = (np.asarray(D[up_idx].sum(axis=0), dtype=np.float64)
               - np.asarray(D[down_idx].sum(axis=0), dtype=np.float64))
        obs_cmp = obs.astype(np.float32)
        p_rev = (np.count_nonzero(null <= obs_cmp, axis=0) + 1.0) / (M + 1)
        fdr_rev = engine._benjamini_hochberg(p_rev)
        fracs.append(float((fdr_rev < 0.05).mean()))
    out["negative_control"] = {
        "n_random_signatures": NEG_CTRL_N,
        "sig_size": [NEG_UP, NEG_DOWN],
        "null_M": M,
        "seed": NEG_SEED,
        "frac_drugs_fdr_lt_0.05_per_sig": fracs,
        "max_frac": max(fracs),
        "mean_frac": float(np.mean(fracs)),
        "pass_lt_1pct": bool(max(fracs) < 0.01),
    }
    log(f"阴性对照：max={max(fracs):.4%} mean={np.mean(fracs):.4%} "
        f"→ {'通过(<1%)' if max(fracs) < 0.01 else '未通过'}")

    out["elapsed_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    log(f"写出 {args.out}")


if __name__ == "__main__":
    main()

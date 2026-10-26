#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7e 阶段 1 · 任务 3（L3 侧）：对 5 个基因用 L3 robust z 算签名。

口径与 backend/signature_engine.py + suitability.py 一致：
- 样本内秩（1 = 最高），KS > 0 = 上调；
- Bootstrap null 来自同一份 L3 数据的 2,000 实例随机背景池（不混用 L5）；
- p = (#|null| >= |obs| + 1) / (B + 1)，BH 校正；
- 显著：FDR < 0.001 且 |KS| > 0.2（现网 v2 生产参数），每方向封顶 50；
- LOHO：k = max(10, 封顶后 up+down)，留一 hairpin（剩余 <3 跳过）取最小 Jaccard；
- 判档：suitability RULE_VERSION 4.5 核心规则（无注释层）。

输入：data/spike_z.npz（02_extract_z.py 产物）
输出：results/03_l3_signatures.json
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (GENES, KS_THRESHOLD, FDR_THRESHOLD, BOOTSTRAP_N,
                    RANDOM_SEED, MAX_GENES_PER_DIRECTION, OUT_DATA,
                    OUT_RESULTS, ks_uniform_batch, benjamini_hochberg,
                    bootstrap_null_ks_batched, rank_columns,
                    loho_jaccard_min, grade_lite)

t0 = time.time()


def log(msg):
    print(f"[{time.time()-t0:7.1f}s] {msg}", flush=True)


d = np.load(os.path.join(OUT_DATA, "spike_z.npz"), allow_pickle=False)
Z = d["Z"]                      # (n_inst, 978)，行序与元数据一致；NaN 排秩时视为最低
is_target = d["is_target"].astype(bool)
pert_iname = d["pert_iname"].astype(str)
pert_id = d["pert_id"].astype(str)
cell_id_arr = d["cell_id"].astype(str)
rna_plate_arr = d["rna_plate"].astype(str)
fallback_arr = d["fallback_level"]
symbols = [str(s) for s in d["lm_symbols"]]
G = len(symbols)
sym_upper = {s.strip().upper(): i for i, s in enumerate(symbols)}

# 背景池秩矩阵（KS null；同一份 L3 数据）
bg_ranks = rank_columns(Z[~is_target].T)        # (978, n_bg)
log(f"背景池 {bg_ranks.shape[1]} 列，秩矩阵完成")

results = {}
# 支持单基因并行：--gene EGFR --out 03_l3_EGFR.json
argv = sys.argv[1:]
only_gene = argv[argv.index("--gene") + 1].upper() if "--gene" in argv else None
out_name = argv[argv.index("--out") + 1] if "--out" in argv else "03_l3_signatures.json"
gene_list = [only_gene] if only_gene else GENES

for gene in gene_list:
    gmask = is_target & (np.char.upper(pert_iname) == gene)
    idx = np.where(gmask)[0]
    n_samples = len(idx)
    if n_samples == 0:
        results[gene] = {"error": "no instances"}
        continue
    ranks = rank_columns(Z[idx].T)              # (978, n)
    observed_ks = ks_uniform_batch(ranks, G)

    rng = np.random.default_rng(RANDOM_SEED)
    null_ks = bootstrap_null_ks_batched(bg_ranks, n_samples, BOOTSTRAP_N, rng)
    obs_abs = np.abs(observed_ks)
    null_abs = np.abs(null_ks)
    p_values = (np.sum(null_abs >= obs_abs, axis=0) + 1) / (BOOTSTRAP_N + 1)
    fdr = benjamini_hochberg(p_values)

    up_sig, down_sig = [], []
    ks_dict = {}
    for i, sym in enumerate(symbols):
        ks = float(observed_ks[i])
        ks_dict[sym] = ks
        if fdr[i] < FDR_THRESHOLD and abs(ks) > KS_THRESHOLD:
            (up_sig if ks > 0 else down_sig).append((sym, ks))
    n_sig = len(up_sig) + len(down_sig)
    up_sig.sort(key=lambda x: x[1], reverse=True)
    down_sig.sort(key=lambda x: x[1])
    up_sig = up_sig[:MAX_GENES_PER_DIRECTION]
    down_sig = down_sig[:MAX_GENES_PER_DIRECTION]

    k = max(10, len(up_sig) + len(down_sig))
    full_top = np.argsort(-obs_abs)[:min(k, G)]
    loho, loho_detail = loho_jaccard_min(ranks, pert_id[idx], full_top, G, k)

    target_ks = ks_dict.get(gene) if gene in sym_upper else None
    n_hairpins = int(len(np.unique(pert_id[idx])))
    grade = grade_lite(n_sig, loho, target_ks, gene in sym_upper, n_hairpins)

    results[gene] = {
        "n_samples": n_samples,
        "n_hairpins": n_hairpins,
        "n_cells": int(len(np.unique(cell_id_arr[idx]))),
        "n_plates": int(len(np.unique(rna_plate_arr[idx]))),
        "n_sig": n_sig,
        "up_genes": [s for s, _ in up_sig],
        "down_genes": [s for s, _ in down_sig],
        "loho_jaccard_min": loho,
        "loho_detail": loho_detail,
        "target_ks": target_ks,
        "grade": grade,
        "bootstrap_n": BOOTSTRAP_N,
        "ks_threshold": KS_THRESHOLD,
        "fdr_threshold": FDR_THRESHOLD,
        "min_p_resolution": 1.0 / (BOOTSTRAP_N + 1),
        "fallback_levels": {str(l): int((fallback_arr[idx] == l).sum())
                            for l in (0, 1, 2)},
        "n_inst_with_nan": int(np.isnan(Z[idx]).any(axis=1).sum()),
    }
    log(f"{gene}: n={n_samples} hairpins={n_hairpins} n_sig={n_sig} "
        f"loho={None if loho is None else round(loho,3)} grade={grade}")

out = os.path.join(OUT_RESULTS, out_name)
with open(out, "w", encoding="utf-8") as fp:
    json.dump(results, fp, ensure_ascii=False, indent=2)
log(f"写出 {out}；总耗时 {(time.time()-t0)/60:.1f} 分钟")

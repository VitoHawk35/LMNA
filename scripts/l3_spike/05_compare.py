#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7e 阶段 1 · 任务 3（合并对比）+ 任务 4（与 v1 z 值相关性）。

- L5 侧：CDK4/EGFR/MTOR 用 ~/lmna_v3_cache 的 b031a48b8a 缓存签名
  （参数与现网 v2 一致：KS 0.2 / FDR 0.001 / B=100000 / ALGO 2）；
  TOP2A/LMNA 用 04_l5_signatures.py 的重算结果；
  另对 CDK4 做缓存 vs 重算的交叉验证。
- 任务 4：抽 3 个实例，本次 robust z（median/MAD）与 v1 _l4zsvc_shrna_z.dat
  （mean/std 口径）逐 978 基因 Pearson r。口径不同不要求一致，r 应明显为正。

输出：results/05_compare.json
"""
import glob
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (GENES, V1_Z_DAT, V1_Z_META, L5_CACHED_SIG_DIR,
                    OUT_DATA, OUT_RESULTS)

t0 = time.time()


def log(msg):
    print(f"[{time.time()-t0:7.1f}s] {msg}", flush=True)


def jaccard(a, b):
    sa, sb = set(a), set(b)
    u = sa | sb
    return len(sa & sb) / len(u) if u else 1.0


# ---------- L5 侧汇总 ----------
l5 = {}
for gene in ["CDK4", "EGFR", "MTOR"]:
    hits = glob.glob(os.path.join(L5_CACHED_SIG_DIR, f"{gene}_*_signature.json"))
    if not hits:
        continue
    with open(hits[0], encoding="utf-8") as fp:
        sig = json.load(fp)
    qc = sig.get("qc", {})
    l5[gene] = {
        "source": f"cached {os.path.basename(hits[0])} (lmna_v3_cache)",
        "n_samples": sig.get("n_samples"),
        "n_hairpins": sig.get("n_hairpins"),
        "n_cells": sig.get("n_cells"),
        "n_sig": sig.get("n_sig"),
        "up_genes": sig.get("up_genes") or [],
        "down_genes": sig.get("down_genes") or [],
        "loho_jaccard_min": sig.get("loho_jaccard_min"),
        "target_ks": (sig.get("ks_scores") or {}).get(gene),
        "grade": qc.get("grade"),
        "params": sig.get("params"),
    }
with open(os.path.join(OUT_RESULTS, "04_l5_summary.json"), encoding="utf-8") as fp:
    recomputed = json.load(fp)
for gene in ["TOP2A", "LMNA"]:
    if gene in recomputed:
        l5[gene] = recomputed[gene]

# CDK4 交叉验证：缓存 vs 重算
xcheck = None
if "CDK4" in recomputed and "CDK4" in l5:
    c, r = l5["CDK4"], recomputed["CDK4"]
    xcheck = {
        "n_sig_cache": c["n_sig"], "n_sig_recomputed": r["n_sig"],
        "loho_cache": c["loho_jaccard_min"], "loho_recomputed": r["loho_jaccard_min"],
        "grade_cache": c["grade"], "grade_recomputed": r["grade"],
        "up_jaccard": jaccard(c["up_genes"], r["up_genes"]),
        "down_jaccard": jaccard(c["down_genes"], r["down_genes"]),
        "n_samples_cache": c["n_samples"], "n_samples_recomputed": r["n_samples"],
    }

# ---------- L3 侧读入 ----------
with open(os.path.join(OUT_RESULTS, "03_l3_signatures.json"), encoding="utf-8") as fp:
    l3 = json.load(fp)

table = {}
for gene in GENES:
    a, b = l3.get(gene), l5.get(gene)
    if not a or not b or "error" in a:
        continue
    table[gene] = {
        "l3": {k: a[k] for k in ("n_samples", "n_hairpins", "n_cells", "n_sig",
                                 "loho_jaccard_min", "target_ks", "grade")},
        "l5": {k: b.get(k) for k in ("n_samples", "n_hairpins", "n_cells",
                                     "n_sig", "loho_jaccard_min", "target_ks",
                                     "grade")},
        "l5_source": b.get("source"),
        "up_jaccard_l3_vs_l5": jaccard(a["up_genes"], b.get("up_genes") or []),
        "down_jaccard_l3_vs_l5": jaccard(a["down_genes"], b.get("down_genes") or []),
    }
log("L3/L5 对比表完成")

# ---------- 任务 4：与 v1 z 比较 ----------
with open(V1_Z_META, encoding="utf-8") as fp:
    meta = json.load(fp)
v1_ids = meta["sig_ids"]
v1_index = {s: i for i, s in enumerate(v1_ids)}
n_pool = int(meta["n_pool"])
z_v1 = np.memmap(V1_Z_DAT, dtype="float32", mode="r", shape=(978, n_pool))

d = np.load(os.path.join(OUT_DATA, "spike_z.npz"), allow_pickle=False)
Z = d["Z"]
inst_ids = d["inst_id"].astype(str)
is_target = d["is_target"].astype(bool)
pert_iname = d["pert_iname"].astype(str)

# 每个目标基因各取 1 个实例（LMNA 优先），共 3 个；另附 2 个背景实例
picks = []
for gene in ["LMNA", "CDK4", "MTOR"]:
    cand = [i for i in np.where(is_target)[0]
            if pert_iname[i].upper() == gene and inst_ids[i] in v1_index]
    if cand:
        picks.append(cand[0])
bg_cand = [i for i in np.where(~is_target)[0] if inst_ids[i] in v1_index][:2]

corr = []
for i in picks + bg_cand:
    mine = Z[i].astype(np.float64)
    theirs = np.asarray(z_v1[:, v1_index[inst_ids[i]]], dtype=np.float64)
    ok = np.isfinite(mine) & np.isfinite(theirs)
    r = float(np.corrcoef(mine[ok], theirs[ok])[0, 1]) if ok.sum() > 10 else None
    corr.append({
        "inst_id": str(inst_ids[i]),
        "role": "target" if bool(is_target[i]) else "background",
        "gene": str(pert_iname[i]) if bool(is_target[i]) else None,
        "pearson_r": r,
        "n_genes_used": int(ok.sum()),
        "fallback_level": int(d["fallback_level"][i]),
    })
    log(f"{inst_ids[i]}: r={r}")

out = {
    "comparison": table,
    "cdk4_crosscheck": xcheck,
    "v1_z_correlation": corr,
    "v1_z_meta": {k: v for k, v in meta.items() if k != "sig_ids"},
}
with open(os.path.join(OUT_RESULTS, "05_compare.json"), "w", encoding="utf-8") as fp:
    json.dump(out, fp, ensure_ascii=False, indent=2)
log(f"写出 {OUT_RESULTS}/05_compare.json")

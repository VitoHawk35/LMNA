#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7f 阶段1 · 覆盖面快速核查（服务器，先于面板跑）

核实两件事并写 JSON：
1. 面板每个靶点在签名侧数据源的 shRNA 实例数 / hairpin 数
   （list_available_genes 口径）；
2. 面板金标准药物别名组在 LINCS 药物矩阵（pert_iname）中的在场情况
   （顺带预热药物中位数矩阵缓存，供 run_panel.py 复用）。

用法：
    DATA_PROVIDER=l3 L3_DERIVED_DIR=/home/keji/l3_tmp/derived/l3_v1 \
    CMAP_DATA_DIR=/home/keji/cmap_v2_data LMNA_CACHE_DIR=/home/keji/l3_tmp/l7f_cache \
    LINCS_INTEGRITY_MODE=off \
    ~/miniconda3/envs/cmap/bin/python -B scripts/l7f_panel/check_coverage.py \
        --side l3 --out /home/keji/l3_tmp/l7f_results/coverage_l3.json
"""

import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "..", "backend"))
for p in (_HERE, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from panel_def import PANEL, TARGETS  # noqa: E402

t0 = time.time()


def log(msg):
    print(f"[{time.time()-t0:8.1f}s] {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", required=True, choices=["l3", "l5"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import config
    from provider_factory import create_provider
    from drug_scorer import DrugScorer

    assert config.DATA_PROVIDER == args.side

    provider = create_provider()
    avail = set(provider.list_available_genes())
    log(f"{args.side} 可用基因 {len(avail)} 个")

    genes = {}
    for t in TARGETS:
        df = provider.get_shrna_samples(t)
        genes[t] = {
            "in_available_genes": t in avail,
            "n_samples": int(len(df)),
            "n_hairpins": int(df["pert_id"].nunique()) if len(df) else 0,
        }
        log(f"[{t}] samples={genes[t]['n_samples']} "
            f"hairpins={genes[t]['n_hairpins']} avail={genes[t]['in_available_genes']}")

    log("构建药物中位数矩阵（首跑会建缓存）...")
    scorer = DrugScorer(provider)
    drug_names = [str(n).strip().lower() for n in scorer._drug_names]
    log(f"药物 {len(drug_names)} 种")

    drugs = {}
    for t in TARGETS:
        groups = []
        for group in PANEL[t]["gold"]:
            present = sorted(v for v in group if v in drug_names)
            groups.append({"aliases": sorted(group), "present": present})
        drugs[t] = groups
        n_hit = sum(1 for g in groups if g["present"])
        log(f"[{t}] 金标准在场 {n_hit}/{len(groups)}")

    out = {"side": args.side, "genes": genes, "gold_drugs": drugs,
           "n_drugs": len(drug_names)}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    log(f"写出 {args.out}")


if __name__ == "__main__":
    main()

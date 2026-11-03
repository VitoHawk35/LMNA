#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L7f：与 L7e 阶段2 四靶点结果交叉核对（服务器本地跑，只读）。"""
import json

STAGE2 = "/home/keji/l3_tmp/stage2/results"
L7F = "/home/keji/l3_tmp/l7f_results"


def load_stage2(side):
    d = json.load(open(f"{STAGE2}/exp1_{side}.json"))
    return {t: r for t, r in d["targets"].items()}


def load_l7f(side):
    import glob
    rows = {}
    for fp in sorted(glob.glob(f"{L7F}/panel_{side}_shard*.json")):
        d = json.load(open(fp))
        rows.update(d.get("targets", {}))
    return rows


def main():
    for side in ("l3", "l5"):
        s2, l7 = load_stage2(side), load_l7f(side)
        print(f"== {side} (L7f 已出 {len(l7)} 靶点)")
        for t in ("CDK4", "EGFR", "MTOR", "BRAF"):
            a = s2[t]
            b = l7.get(t)
            if b is None:
                print(f"{t:6s} L7e: n_sig={a['n_sig']} loho={a['loho_jaccard_min']:.4f} "
                      f"auroc={a['auroc_self']:.4f} grade={a['grade']} | L7f: 未出")
                continue
            same = (a["n_sig"] == b["n_sig"]
                    and abs(a["loho_jaccard_min"] - b["loho_jaccard_min"]) < 1e-9
                    and abs(a["auroc_self"] - b["auroc_self"]) < 1e-9
                    and a["grade"] == b["grade"])
            print(f"{t:6s} {'MATCH' if same else 'DIFF'} "
                  f"L7e(n={a['n_sig']},loho={a['loho_jaccard_min']:.4f},"
                  f"auroc={a['auroc_self']:.4f},{a['grade']}) "
                  f"L7f(n={b['n_sig']},loho={b['loho_jaccard_min']:.4f},"
                  f"auroc={b['auroc_self']:.4f},{b['grade']})")


if __name__ == "__main__":
    main()

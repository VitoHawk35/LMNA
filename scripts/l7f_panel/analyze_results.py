#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7f 阶段1 · 结果分析：合并分片 JSON → 四元组总表 → 候选方案对比

本地运行（不依赖服务器数据文件，只读 l7f_results 的分片 JSON）：
    python -I scripts/l7f_panel/analyze_results.py \
        --l3 /path/to/l7f_results --l5 /path/to/l7f_results \
        --out analysis.json

输入目录内找 panel_<side>_shard*.json 合并。每个靶点只应出现一个分片。

候选方案（都只放宽黄档、从不收紧 → 结构上无降档；脚本仍逐格断言单调性）：
- current（4.5 现状）：黄 = n_sig≥20 且 0.3≤LOHO<0.5；空隙区 → 红
- A：黄档 n_sig 下限 20→5（空隙整体并入黄档）
- Bθ（θ∈{0.35,0.40,0.45}）：空隙分层——n_sig∈[5,20) 时黄档要求 LOHO≥θ，
  n_sig≥20 仍按 0.3
- C：连续斜坡——黄档要求 LOHO ≥ max(0.3, 0.55 − 0.02×n_sig)
  （n_sig=5→0.45，n_sig=10→0.35，n_sig≥13→0.3；空隙区按签名量平滑放宽）

输出 analysis.json：四元组总表（两侧）、各方案判档、单调性断言结果、
空隙区分析、判档↔AUROC 一致性指标、阴性对照复核、L5 回退检查。
stdout 打印报告用 markdown 表。
"""

import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "..", "backend"))
for p in (_HERE, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from panel_def import PANEL, TARGETS  # noqa: E402

GRADE_RANK = {"red": 0, "yellow": 1, "green": 2}
MIN_SIG, J_GREEN, J_RED = 5, 0.5, 0.3
YELLOW_MIN_SIG_CURRENT = 20


def core_grade(n_sig, loho, scheme):
    """只含 n_sig/LOHO 核心规则的判档（注释层/D1 防线与方案无关，不在此列）。

    与 suitability.grade() 的档位语义一致：先硬红线，再绿，再黄，否则红。
    """
    if loho is None or n_sig < MIN_SIG or loho < J_RED:
        return "red"
    if loho >= J_GREEN:
        return "green"          # n_sig≥5 已在上面保证
    # 0.3 <= loho < 0.5
    if scheme == "current":
        return "yellow" if n_sig >= YELLOW_MIN_SIG_CURRENT else "red"
    if scheme == "A":
        return "yellow"
    if scheme.startswith("B"):
        theta = float(scheme[1:]) / 100.0
        return "yellow" if (n_sig >= YELLOW_MIN_SIG_CURRENT or loho >= theta) else "red"
    if scheme == "C":
        thr = max(J_RED, 0.55 - 0.02 * n_sig)
        return "yellow" if loho >= thr else "red"
    raise ValueError(scheme)


SCHEMES = ["current", "A", "B35", "B40", "B45", "C"]


def check_monotonicity(scheme):
    """网格断言：固定 LOHO 时 n_sig 增大不得降档；固定 n_sig 时 LOHO 增大
    不得降档。返回违规列表（应为空）。"""
    violations = []
    ns = list(range(0, 61))
    ls = [round(0.30 + 0.005 * i, 3) for i in range(0, 141)]  # 0.30..1.00
    for loho in ls:
        prev = None
        for n in ns:
            g = GRADE_RANK[core_grade(n, loho, scheme)]
            if prev is not None and g < prev:
                violations.append(("n_sig", n, loho))
            prev = g
    for n in ns:
        prev = None
        for loho in ls:
            g = GRADE_RANK[core_grade(n, loho, scheme)]
            if prev is not None and g < prev:
                violations.append(("loho", n, loho))
            prev = g
    return violations


def spearman(x, y):
    xs = pd.Series(x).rank(method="average").to_numpy()
    ys = pd.Series(y).rank(method="average").to_numpy()
    if len(xs) < 3 or np.std(xs) == 0 or np.std(ys) == 0:
        return None
    return float(np.corrcoef(xs, ys)[0, 1])


def load_side(res_dir, side):
    rows, neg, params, thresholds = {}, {}, None, None
    for fp in sorted(glob.glob(os.path.join(res_dir, f"panel_{side}_shard*.json"))):
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        params = params or d.get("params")
        thresholds = thresholds or d.get("grading_thresholds")
        for t, rec in d.get("targets", {}).items():
            assert t not in rows, f"{t} 在多个分片重复: {fp}"
            rows[t] = rec
        if d.get("negative_control"):
            neg = d["negative_control"]
    return rows, neg, params, thresholds


def scheme_metrics(rows, scheme):
    """某方案下：判档分布、各档 AUROC 均值、Spearman(档, AUROC)、
    空隙区靶点清单及其 AUROC、难度对照是否仍红。"""
    graded, gap = {}, []
    for t, rec in rows.items():
        g = core_grade(rec["n_sig"], rec["loho_jaccard_min"], scheme)
        graded[t] = g
        n, l = rec["n_sig"], rec["loho_jaccard_min"]
        if l is not None and MIN_SIG <= n < YELLOW_MIN_SIG_CURRENT and J_RED <= l < J_GREEN:
            gap.append(t)
    dist = {g: sum(1 for v in graded.values() if v == g) for g in GRADE_RANK}
    auc_by_grade, xs, ys = {}, [], []
    for t, g in graded.items():
        a = rows[t]["auroc_self"]
        if a is None:
            continue
        auc_by_grade.setdefault(g, []).append(a)
        xs.append(GRADE_RANK[g])
        ys.append(a)
    difficulty = [t for t in ("TP53", "MYC", "LMNA") if t in rows]
    return {
        "grades": graded,
        "dist": dist,
        "gap_targets": sorted(gap),
        "gap_aurocs": {t: rows[t]["auroc_self"] for t in sorted(gap)},
        "auroc_mean_by_grade": {
            g: float(np.mean(v)) for g, v in auc_by_grade.items()},
        "spearman_grade_auroc": spearman(xs, ys),
        "difficulty_still_red": all(graded[t] == "red" for t in difficulty),
        "difficulty_grades": {t: graded[t] for t in difficulty},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--l3", required=True, help="l7f_results 目录（L3 分片所在）")
    ap.add_argument("--l5", required=True, help="l7f_results 目录（L5 分片所在）")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    l3, neg3, params3, thr3 = load_side(args.l3, "l3")
    l5, neg5, params5, thr5 = load_side(args.l5, "l5")

    missing3 = [t for t in TARGETS if t not in l3]
    missing5 = [t for t in TARGETS if t not in l5]
    print(f"L3 靶点 {len(l3)}/{len(TARGETS)}，缺 {missing3}")
    print(f"L5 靶点 {len(l5)}/{len(TARGETS)}，缺 {missing5}")

    # ---- 单调性断言 ----
    mono = {s: check_monotonicity(s) for s in SCHEMES}
    for s, v in mono.items():
        print(f"单调性[{s}]: {'通过' if not v else f'违规 {v[:5]}'}")

    # ---- 各方案指标（两侧） ----
    res = {"monotonicity": {s: (not v) for s, v in mono.items()},
           "params_l3": params3, "params_l5": params5,
           "thresholds": thr3, "sides": {}}
    for side, rows in (("l3", l3), ("l5", l5)):
        res["sides"][side] = {
            "neg_ctrl": neg3 if side == "l3" else neg5,
            "per_scheme": {s: scheme_metrics(rows, s) for s in SCHEMES},
            "tuples": {
                t: {
                    "n_sig": r["n_sig"], "loho": r["loho_jaccard_min"],
                    "auroc": r["auroc_self"], "grade45": r["grade"],
                    "n_samples": r["n_samples"], "n_hairpins": r["n_hairpins"],
                } for t, r in rows.items()},
        }

    # ---- 回退检查：新方案相对 current 不得有任何降档（两侧都查） ----
    regress = {}
    for side in ("l3", "l5"):
        per = res["sides"][side]["per_scheme"]
        for s in SCHEMES:
            if s == "current":
                continue
            down = [t for t in TARGETS
                    if t in per["current"]["grades"]
                    and GRADE_RANK[per[s]["grades"][t]]
                    < GRADE_RANK[per["current"]["grades"][t]]]
            regress[f"{side}:{s}"] = down
    res["no_downgrade_check"] = regress

    # ---- markdown 总表 ----
    def fmt(v, nd=3):
        return "—" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))

    print("\n## 四元组总表\n")
    print("| 靶点 | 角色/预期 | L3 n_sig | L3 LOHO | L3 AUROC | L3 档(4.5) | "
          "L5 n_sig | L5 LOHO | L5 AUROC | L5 档(4.5) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for t in TARGETS:
        r3, r5 = l3.get(t), l5.get(t)
        role = PANEL[t]["role"] + "/" + PANEL[t]["expected"]
        print(f"| {t} | {role} | "
              f"{r3['n_sig'] if r3 else '—'} | {fmt(r3['loho_jaccard_min']) if r3 else '—'} | "
              f"{fmt(r3['auroc_self']) if r3 else '—'} | {r3['grade'] if r3 else '—'} | "
              f"{r5['n_sig'] if r5 else '—'} | {fmt(r5['loho_jaccard_min']) if r5 else '—'} | "
              f"{fmt(r5['auroc_self']) if r5 else '—'} | {r5['grade'] if r5 else '—'} |")

    with open(args.out, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=2)
    print(f"\n写出 {args.out}")


if __name__ == "__main__":
    main()

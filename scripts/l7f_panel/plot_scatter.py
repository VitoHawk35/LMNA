"""L7f: (n_sig, LOHO) scatter colored by AUROC, L3/L5 small multiples.

Static PNG companion to docs/design/L7f-规则表重校准.md section 4.
Data source: local_results/analysis.json (produced by analyze_results.py).

Run (local):
    PYTHONIOENCODING=utf-8 D:/mine_Anaconda3/python.exe -I \
        scripts/l7f_panel/plot_scatter.py \
        --analysis scripts/l7f_panel/local_results/analysis.json \
        --out scripts/l7f_panel/local_results/scatter_nsif_loho.png
"""

import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle

GRADES_ZH = {"green": "green", "yellow": "yellow", "red": "red"}
# gap zone of RULE_VERSION 4.5: n_sig in [5,20) and LOHO in [0.3,0.5)
GAP = dict(x0=5, x1=20, y0=0.3, y1=0.5)

# per-(side, target) label offsets in points, tuned to avoid collisions
LABEL_OFFSETS = {
    ("l3", "CDK2"): (-34, 6),
    ("l3", "PIK3CA"): (8, -12),
    ("l3", "ALK"): (-30, -2),
    ("l3", "HDAC1"): (-16, -17),
    ("l3", "FGFR1"): (8, -12),
    ("l3", "EGFR"): (8, 6),
    ("l5", "MET"): (-30, 6),
    ("l5", "PLK1"): (8, 6),
    ("l5", "TP53"): (8, -13),
    ("l5", "LMNA"): (8, 4),
    ("l3", "LMNA"): (8, 4),
    ("l3", "MAP2K1"): (8, -13),
    ("l5", "MAP2K1"): (8, -13),
}
DEFAULT_OFFSET = (7, 5)


def load(analysis_path):
    with open(analysis_path, encoding="utf-8") as f:
        return json.load(f)


def panel_points(tuples):
    pts = []
    for target, t in tuples.items():
        pts.append(
            dict(
                target=target,
                n_sig=t["n_sig"],
                loho=t["loho"],
                auroc=t["auroc"],
                grade=t["grade45"],
            )
        )
    return pts


def in_gap(p):
    return GAP["x0"] <= p["n_sig"] < GAP["x1"] and GAP["y0"] <= p["loho"] < GAP["y1"]


def draw(ax, pts, title, norm, cmap, side):
    ax.set_title(title, fontsize=11)
    # gap-zone highlight + rule boundary lines
    ax.add_patch(
        Rectangle(
            (GAP["x0"], GAP["y0"]),
            GAP["x1"] - GAP["x0"],
            GAP["y1"] - GAP["y0"],
            facecolor="#888888",
            alpha=0.12,
            zorder=0,
        )
    )
    for x in (5, 20):
        ax.axvline(x, color="#999999", lw=0.8, ls="--", zorder=1)
    for y in (0.3, 0.5):
        ax.axhline(y, color="#999999", lw=0.8, ls="--", zorder=1)
    ax.text(
        12.5,
        0.51,
        "gap zone 4.5 -> red",
        ha="center",
        va="bottom",
        fontsize=8,
        color="#666666",
    )

    labeled = set()
    for p in pts:
        if p["auroc"] is None:
            ax.scatter(
                p["n_sig"],
                p["loho"],
                facecolors="none",
                edgecolors="#666666",
                s=64,
                lw=1.4,
                zorder=3,
            )
        else:
            ax.scatter(
                p["n_sig"],
                p["loho"],
                c=[p["auroc"]],
                cmap=cmap,
                norm=norm,
                s=64,
                edgecolors="white",
                lw=0.8,
                zorder=3,
            )
        # selective direct labels: gap-zone members + notable boundary cases
        if in_gap(p) or p["target"] in ("MAP2K1", "TP53", "MYC", "LMNA"):
            off = LABEL_OFFSETS.get((side, p["target"]), DEFAULT_OFFSET)
            ax.annotate(
                p["target"],
                (p["n_sig"], p["loho"]),
                textcoords="offset points",
                xytext=off,
                fontsize=8,
                color="#333333",
            )
            labeled.add(p["target"])

    ax.set_xlabel("n_sig (FDR+KS pass, pre-cap)", fontsize=10)
    ax.set_xlim(-2, 110)
    ax.set_ylim(0, 0.9)
    ax.grid(True, color="#dddddd", lw=0.5, zorder=0)
    ax.tick_params(labelsize=9, colors="#444444")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    return labeled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data = load(args.analysis)
    cmap = plt.get_cmap("coolwarm")
    # AUROC has a meaningful midpoint (0.5 = chance) -> diverging norm
    norm = TwoSlopeNorm(vmin=0.25, vcenter=0.5, vmax=1.0)

    fig, axes = plt.subplots(
        1, 2, figsize=(11.5, 4.8), sharey=True, constrained_layout=True
    )
    for ax, side in zip(axes, ("l3", "l5")):
        pts = panel_points(data["sides"][side]["tuples"])
        draw(ax, pts, f"{side.upper()} signature side", norm, cmap, side)
    axes[0].set_ylabel("LOHO Jaccard (min over hairpins)", fontsize=10)

    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sm, ax=axes, shrink=0.85, pad=0.02)
    cb.set_label("AUROC (own gold inhibitors, mimic)", fontsize=9)
    cb.ax.tick_params(labelsize=8)

    # manual legend entries
    axes[0].scatter([], [], facecolors="none", edgecolors="#666666", s=64, lw=1.4, label="no gold list")
    axes[0].legend(loc="lower right", fontsize=8, frameon=False)

    fig.suptitle(
        "L7f panel (21 targets): grading-rule 4.5 gap zone vs AUROC",
        fontsize=12,
    )
    fig.savefig(args.out, dpi=160)
    print(f"saved: {args.out}")


if __name__ == "__main__":
    main()

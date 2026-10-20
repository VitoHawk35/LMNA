#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
D2：从 24MB 完整夹具截出 <=3MB 的 mini 夹具（入库到 backend/tests/data/mini_fixture/）。

用法（本机，需先备好完整夹具）：

    python backend/tests/make_mini_fixture.py \
        --full-dir /path/to/full_fixture \
        --out-dir  backend/tests/data/mini_fixture

裁剪规则（固定种子 42，与 make_fixture.py 的种子约定一致）：
- 978 个 landmark 基因全部保留；
- 4 个基准靶点（CDK4 / TOP2A / EGFR / MTOR，以完整夹具 meta 为准）的全部
  shRNA 列保留；
- ABHD4（3 个样本、1 个 hairpin）保留，用于 L3 数据门槛与 /compute 422 测试；
- 其余背景 shRNA 用 np.random.default_rng(42) 无放回抽 600 条；
- 300 个药物 = 4 个靶点已知抑制剂的并集（88 个，来自完整夹具 meta）+
  其余药物用同一种子补足；
- 矩阵按 int16 千分位 z（milli-z）存储，npz 内含 value_scale=0.001，
  FixtureProvider 加载时乘回；数值误差 <=0.0005，z 语义不变。

expected 值（lmna_fixture_expected.json）：
- 与完整夹具同一生成方式：修正后的算法、固定种子 RANDOM_SEED=42、
  BOOTSTRAP_N=1000、FAST_MODE_TOP_N=0、MAX_GENES_PER_DIRECTION=50，
  每个靶点新建一个 SignatureEngine（与 test_fixture_regression.py 一致）。
- 背景池变小后 n_sig 会变，mini 使用自己的 expected，不与完整夹具混用。
"""

import argparse
import io
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]

TARGETS = ("CDK4", "TOP2A", "EGFR", "MTOR")
EXTRA_GENES = ("ABHD4",)          # 单 hairpin 基因：L3 门槛/422 测试
EXPECTED_GENES = ("CDK4", "TOP2A", "EGFR")   # 与完整夹具 expected 覆盖一致
SEED = 42
N_NULL = 600
N_DRUGS = 300
VALUE_SCALE = 0.001               # int16 milli-z


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def select_columns(full_dir, n_null, n_drugs, seed):
    with np.load(os.path.join(full_dir, "lmna_fixture.npz")) as z:
        gene_symbols = z["gene_symbols"]
        sh_matrix = z["sh_matrix"]
        cp_matrix = z["cp_matrix"]

    sh_df = pd.read_csv(
        os.path.join(full_dir, "lmna_fixture_sh.tsv"), sep="\t", dtype=str
    )
    cp_df = pd.read_csv(
        os.path.join(full_dir, "lmna_fixture_cp.tsv"), sep="\t", dtype=str
    )
    with open(os.path.join(full_dir, "lmna_fixture_meta.json"), encoding="utf-8") as f:
        meta = json.load(f)

    missing_targets = [g for g in TARGETS if g not in meta.get("targets", {})]
    if missing_targets:
        raise RuntimeError(f"完整夹具 meta 缺少基准靶点: {missing_targets}")

    # ---- shRNA 列：4 靶点 + ABHD4 全保留，背景抽 n_null 条 ----
    keep = set(TARGETS) | set(EXTRA_GENES)
    target_mask = sh_df["pert_iname"].isin(keep).to_numpy()
    for gene in sorted(keep):
        sub = sh_df[sh_df["pert_iname"] == gene]
        log(f"[mini] {gene}: {len(sub)} 个 shRNA 样本, "
            f"{sub['pert_id'].nunique()} 个 hairpin")
        if len(sub) == 0:
            raise RuntimeError(f"{gene} 在完整夹具中没有 shRNA 样本")

    bg_idx = np.flatnonzero(~target_mask)
    if len(bg_idx) < n_null:
        raise RuntimeError(f"背景 shRNA 不足: {len(bg_idx)} < {n_null}")
    rng = np.random.default_rng(seed)
    bg_sel = np.sort(rng.choice(bg_idx, size=n_null, replace=False))
    sh_sel = np.concatenate([np.flatnonzero(target_mask), bg_sel])

    # ---- 药物列：4 靶点已知抑制剂并集 + 补足到 n_drugs ----
    inhibitors = set()
    for gene in TARGETS:
        inhibitors.update(meta["inhibitors"].get(gene, []))
    cp_names = cp_df["pert_iname"].tolist()
    missing_inhib = inhibitors - set(cp_names)
    if missing_inhib:
        raise RuntimeError(f"已知抑制剂不在完整夹具药物表中: {sorted(missing_inhib)}")

    inhib_idx = [i for i, name in enumerate(cp_names) if name in inhibitors]
    rest_idx = np.array(
        [i for i in range(len(cp_names)) if i not in set(inhib_idx)],
        dtype=np.int64,
    )
    n_fill = n_drugs - len(inhib_idx)
    if n_fill < 0:
        raise RuntimeError(f"抑制剂数 {len(inhib_idx)} 已超过 n_drugs={n_drugs}")
    rng2 = np.random.default_rng(seed)
    fill = np.sort(rng2.choice(len(rest_idx), size=n_fill, replace=False))
    cp_sel = np.sort(np.concatenate([inhib_idx, rest_idx[fill]]))
    log(f"[mini] 药物: {len(inhib_idx)} 个已知抑制剂 + {n_fill} 个补足 = {len(cp_sel)}")

    sh_sub_df = sh_df.iloc[sh_sel].reset_index(drop=True)
    cp_sub_df = cp_df.iloc[cp_sel].reset_index(drop=True)

    return {
        "gene_symbols": gene_symbols,
        "sh_matrix": sh_matrix[:, sh_sel],
        "cp_matrix": cp_matrix[:, cp_sel],
        "sh_df": sh_sub_df,
        "cp_df": cp_sub_df,
        "meta": meta,
        "n_inhibitors": len(inhib_idx),
    }


def build_meta(parts, seed):
    full_meta = parts["meta"]
    targets = {}
    for gene in TARGETS:
        info = dict(full_meta["targets"][gene])
        sub = parts["sh_df"][parts["sh_df"]["pert_iname"] == gene]
        info["n_shrna_samples"] = int(len(sub))
        info["n_hairpins"] = int(sub["pert_id"].nunique())
        targets[gene] = info

    extra = {}
    for gene in EXTRA_GENES:
        sub = parts["sh_df"][parts["sh_df"]["pert_iname"] == gene]
        extra[gene] = {
            "n_shrna_samples": int(len(sub)),
            "n_hairpins": int(sub["pert_id"].nunique()),
            "note": "单 hairpin 基因，用于 L3 数据门槛与 /compute 422 测试",
        }

    return {
        "source": full_meta.get("source", ""),
        "generated_by": "backend/tests/make_mini_fixture.py",
        "mini_of": full_meta.get("generated_by", "backend/tests/make_fixture.py"),
        "seed": seed,
        "n_genes": int(len(parts["gene_symbols"])),
        "n_sh": int(len(parts["sh_df"])),
        "n_cp": int(len(parts["cp_df"])),
        "value_scale": VALUE_SCALE,
        "storage": "int16 milli-z（加载时乘 value_scale）",
        "targets": targets,
        "extra_genes": extra,
        "inhibitors": {g: targets[g]["inhibitors"] for g in TARGETS},
    }


def write_fixture(parts, meta, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    sh_milli = np.round(parts["sh_matrix"] / VALUE_SCALE).astype(np.int16)
    cp_milli = np.round(parts["cp_matrix"] / VALUE_SCALE).astype(np.int16)

    npz_buf = io.BytesIO()
    np.savez_compressed(
        npz_buf,
        gene_symbols=parts["gene_symbols"],
        sh_matrix=sh_milli,
        cp_matrix=cp_milli,
        value_scale=np.float32(VALUE_SCALE),
    )
    with open(os.path.join(out_dir, "lmna_fixture.npz"), "wb") as f:
        f.write(npz_buf.getvalue())

    parts["sh_df"].to_csv(
        os.path.join(out_dir, "lmna_fixture_sh.tsv"), sep="\t", index=False
    )
    parts["cp_df"].to_csv(
        os.path.join(out_dir, "lmna_fixture_cp.tsv"), sep="\t", index=False
    )
    with open(os.path.join(out_dir, "lmna_fixture_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    size = sum(
        os.path.getsize(os.path.join(out_dir, n)) for n in os.listdir(out_dir)
    )
    log(f"[mini] 已写入 {out_dir}（不含 expected 时总大小 {size/1e6:.2f} MB）")


def generate_expected(out_dir):
    """与完整夹具 expected 同法生成：B=1000、封顶 50、固定种子、每靶点新 engine。"""
    os.environ["LMNA_FIXTURE_DIR"] = str(out_dir)
    os.environ["DATA_PROVIDER"] = "fixture"
    os.environ["BOOTSTRAP_N"] = "1000"
    os.environ["FAST_MODE_TOP_N"] = "0"
    os.environ["MAX_GENES_PER_DIRECTION"] = "50"
    cache_dir = tempfile.mkdtemp(prefix="lmna-mini-expected-cache-")
    os.environ["LMNA_CACHE_DIR"] = cache_dir

    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from fixture_provider import FixtureProvider
    from signature_engine import SignatureEngine

    provider = FixtureProvider(str(out_dir))
    expected = {}
    for gene in EXPECTED_GENES:
        sig = SignatureEngine(provider).compute_signature(gene)
        expected[gene] = {
            "up_genes": sig["up_genes"],
            "down_genes": sig["down_genes"],
            "target_ks": sig["ks_scores"][gene],
            "n_sig": sig["n_sig"],
            "target_loho": sig["loho_jaccard_min"],
        }
        log(f"[mini] expected {gene}: n_sig={sig['n_sig']} "
            f"target_ks={sig['ks_scores'][gene]:.4f} "
            f"loho={sig['loho_jaccard_min']:.4f} grade={sig['qc']['grade']}")

    with open(os.path.join(out_dir, "lmna_fixture_expected.json"), "w", encoding="utf-8") as f:
        json.dump(expected, f, ensure_ascii=False, indent=1)
    return expected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-dir", required=True, help="24MB 完整夹具目录")
    parser.add_argument(
        "--out-dir",
        default=str(BACKEND_DIR / "tests" / "data" / "mini_fixture"),
    )
    parser.add_argument("--n-null", type=int, default=N_NULL)
    parser.add_argument("--n-drugs", type=int, default=N_DRUGS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--skip-expected", action="store_true",
        help="只写数据文件，不生成 expected（默认会生成）",
    )
    args = parser.parse_args()

    parts = select_columns(args.full_dir, args.n_null, args.n_drugs, args.seed)
    meta = build_meta(parts, args.seed)
    write_fixture(parts, meta, args.out_dir)

    if not args.skip_expected:
        expected = generate_expected(args.out_dir)
        log("[mini] expected 已生成: "
            + json.dumps({g: e["n_sig"] for g, e in expected.items()}))

    total = sum(
        os.path.getsize(os.path.join(args.out_dir, n))
        for n in os.listdir(args.out_dir)
    )
    log(f"[mini] 完成，总大小 {total/1e6:.2f} MB（硬约束 <= 3MB）")
    if total > 3 * 1024 * 1024:
        raise RuntimeError("mini 夹具超过 3MB 硬约束")


if __name__ == "__main__":
    main()

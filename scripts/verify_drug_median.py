#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L8 · 药物中位数缓存复核脚本（部署重建后由人执行，只读）。

用途
----
检查 ~/LMNA/cache/_drug_median_matrix.npy 是否与 GCTX 真值一致：

  1. 默认真值 = 缓存来源数据（GSE92742 Level5 GCTX）：对抽样的药物，
     按其全部/抽样 signature 在 GCTX 中取 landmark 基因列，算中位数，
     与缓存中该药物的 978 维向量求 Pearson r。修复正确的缓存应 ≈ 1.0。
  2. 可选 --beta-dir：再与 LINCS2020 beta Level5 的药物中位数比较
     （不同数据集，r 只作趋势参考，不设硬阈值）。

同时打印行序诊断：row_gene_ids.csv 与 GCTX ROW 顺序是否一致。
L8 实测发现行序也错位；若此处显示 [FAIL]，缓存行标签会是错的，r 会接近 0，
需先修 row_gene_ids.csv（fix_col_names.py --fix-rows）再重建缓存。

用法
----
    # 修复并重建缓存后（在服务器上，只读本脚本）
    python scripts/verify_drug_median.py --n-drugs 5

    # 指定药物 / 更多抽样 / beta 对照
    python scripts/verify_drug_median.py --drug vorinostat --max-sigs-per-drug 200
    python scripts/verify_drug_median.py --beta-dir /data2/wanggang/camp/level5

退出码：默认真值相关系数低于 --min-corr（默认 0.99）时返回 1。
依赖：h5py、numpy、pandas。
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

DEFAULT_DATA_DIR = os.path.expanduser("~/cmap/cmap_data")
DEFAULT_CACHE_DIR = os.path.expanduser("~/LMNA/cache")
DEFAULT_GCTX_NAME = "GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx"
LMNA_CACHE_MATRIX = "_drug_median_matrix.npy"
LMNA_CACHE_NAMES = "_drug_names.csv"


def _require_h5py():
    try:
        import h5py
    except ImportError:
        sys.exit("需要 h5py：请在服务器 cmap 环境执行（source ~/miniconda3/etc/profile.d/conda.sh && conda activate cmap）")
    return h5py


def _decode(values):
    return [v.decode() if isinstance(v, bytes) else str(v) for v in values]


def _pearson(a, b):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 3:
        return float("nan")
    a = a[mask]
    b = b[mask]
    if np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _load_landmark_genes(data_dir):
    gene_info = pd.read_csv(
        os.path.join(data_dir, "GSE92742_Broad_LINCS_gene_info.txt.gz"), sep="\t"
    )
    lm = gene_info[gene_info["pr_is_lm"] == 1].copy()
    return (
        lm["pr_gene_id"].astype(str).tolist(),
        lm["pr_gene_symbol"].astype(str).tolist(),
    )


def _gctx_meta(h5py, path):
    with h5py.File(path, "r") as f:
        col_ids = _decode(f["0/META/COL/id"][:])
        row_ids = _decode(f["0/META/ROW/id"][:])
        shape = tuple(f["0/DATA/0/matrix"].shape)
    return col_ids, row_ids, shape


def _read_gctx_columns(h5py, path, col_positions, gene_positions):
    """按 GCTX 列位置读取 (n_cols, n_genes)，恢复为传入顺序。"""
    col_positions = np.asarray(col_positions, dtype=np.int64)
    gene_positions = np.asarray(gene_positions, dtype=np.int64)
    with h5py.File(path, "r") as f:
        dataset = f["0/DATA/0/matrix"]
        block = dataset[col_positions][:, gene_positions]
    return np.asarray(block, dtype=np.float32)


def _median_from_gctx(h5py, gctx_path, sig_ids, col_pos, gene_positions,
                      max_sigs, rng):
    avail = [s for s in sig_ids if s in col_pos]
    if not avail:
        return None, 0
    if max_sigs and len(avail) > max_sigs:
        picked = rng.choice(len(avail), size=max_sigs, replace=False)
        avail = [avail[i] for i in sorted(picked)]
    positions = [col_pos[s] for s in avail]
    block = _read_gctx_columns(h5py, gctx_path, positions, gene_positions)
    with np.errstate(all="ignore"):
        return np.nanmedian(block, axis=0), len(avail)


def _drug_to_sigs(siginfo, name_col, sig_col, pert_type):
    df = siginfo[siginfo["pert_type"] == pert_type]
    df = df[df[name_col].notna()]
    out = {}
    for name, sid in zip(df[name_col].astype(str), df[sig_col].astype(str)):
        out.setdefault(name, []).append(sid)
    return out


def main():
    parser = argparse.ArgumentParser(description="复核 LMNA 药物中位数缓存与 GCTX 真值的一致性")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--truth-gctx", default=None,
                        help="真值 GCTX（默认 data-dir 下 GSE92742 Level5）")
    parser.add_argument("--n-drugs", type=int, default=5)
    parser.add_argument("--drug", default=None, help="只复核指定药物名（pert_iname）")
    parser.add_argument("--max-sigs-per-drug", type=int, default=200,
                        help="每个药物最多抽样多少个 signature（0 = 全部，较慢）")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-corr", type=float, default=0.99)
    parser.add_argument("--beta-dir", default=None,
                        help="可选：LINCS2020 beta Level5 目录，用于趋势对照")
    args = parser.parse_args()

    h5py = _require_h5py()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    cache_dir = os.path.abspath(os.path.expanduser(args.cache_dir))
    gctx_path = args.truth_gctx or os.path.join(data_dir, DEFAULT_GCTX_NAME)
    cache_matrix_path = os.path.join(cache_dir, LMNA_CACHE_MATRIX)
    cache_names_path = os.path.join(cache_dir, LMNA_CACHE_NAMES)

    for p in (gctx_path, cache_matrix_path, cache_names_path):
        if not os.path.exists(p):
            sys.exit(f"文件不存在: {p}")

    cache = np.load(cache_matrix_path, mmap_mode="r")
    names = pd.read_csv(cache_names_path)["drug_name"].astype(str).tolist()
    if cache.ndim != 2 or cache.shape[1] != len(names):
        sys.exit(f"缓存形状 {cache.shape} 与药物名数量 {len(names)} 不一致")

    gene_ids, gene_symbols = _load_landmark_genes(data_dir)
    if cache.shape[0] != len(gene_ids):
        print(f"[WARN] 缓存行数 {cache.shape[0]} 与 landmark 基因数 {len(gene_ids)} 不一致")

    gctx_cols, gctx_rows, gctx_shape = _gctx_meta(h5py, gctx_path)
    print(f"[verify] GCTX={gctx_path} shape={gctx_shape}")
    print(f"[verify] cache={cache_matrix_path} shape={tuple(cache.shape)}")

    # ---- 行序诊断（只读）----
    row_path = os.path.join(data_dir, "row_gene_ids.csv")
    if os.path.exists(row_path):
        row_csv = pd.read_csv(row_path)["gene_id"].astype(str).tolist()
        same = sum(a == b for a, b in zip(row_csv, gctx_rows))
        print(f"[verify] 行序诊断: row_gene_ids.csv vs GCTX ROW 同位置一致 "
              f"{same}/{min(len(row_csv), len(gctx_rows))}")
        if same != len(gctx_rows):
            print("         [FAIL] 行序错位：缓存的行标签不可信，r 很可能接近 0。")
            print("         先运行 scripts/fix_col_names.py --fix-rows 并重建缓存。")
        else:
            print("         [OK] 行序一致")
    row_pos = {g: i for i, g in enumerate(gctx_rows)}
    missing = [g for g in gene_ids if g not in row_pos]
    if missing:
        sys.exit(f"{len(missing)} 个 landmark 基因不在 GCTX ROW 中，例如 {missing[:3]}")
    gene_positions = [row_pos[g] for g in gene_ids]

    sig_info = pd.read_csv(
        os.path.join(data_dir, "GSE92742_Broad_LINCS_sig_info.txt.gz"),
        sep="\t", low_memory=False,
    )
    drug_to_sigs = _drug_to_sigs(sig_info, "pert_iname", "sig_id", "trt_cp")

    candidates = [n for n in names if n in drug_to_sigs]
    if args.drug:
        candidates = [n for n in candidates if n == args.drug]
    if not candidates:
        sys.exit("缓存中的药物名与 sig_info 的 trt_cp 没有交集，无法复核")
    rng = np.random.default_rng(args.seed)
    if args.drug is None and len(candidates) > args.n_drugs:
        picked = rng.choice(len(candidates), size=args.n_drugs, replace=False)
        candidates = [candidates[i] for i in sorted(picked)]

    col_pos = {s: i for i, s in enumerate(gctx_cols)}
    verdicts = []
    print("\n[verify] 与 GSE92742 Level5 真值比较（缓存来源）：")
    for name in candidates:
        truth, used = _median_from_gctx(
            h5py, gctx_path, drug_to_sigs[name], col_pos, gene_positions,
            args.max_sigs_per_drug, rng,
        )
        if truth is None:
            print(f"  - {name}: GCTX 中无可用 signature，跳过")
            continue
        idx = names.index(name)
        r = _pearson(cache[:, idx], truth)
        verdicts.append(r)
        ok = "[OK]" if np.isfinite(r) and r >= args.min_corr else "[FAIL]"
        print(f"  {ok} {name}: r={r:.4f}  (使用 {used} 个 signature)")

    finite = [r for r in verdicts if np.isfinite(r)]
    if finite:
        print(f"\n[verify] 汇总: n={len(finite)}  min={min(finite):.4f}  "
              f"median={float(np.median(finite)):.4f}  max={max(finite):.4f}")

    # ---- 可选：beta Level5 趋势对照 ----
    if args.beta_dir:
        beta_dir = os.path.abspath(os.path.expanduser(args.beta_dir))
        beta_siginfo_path = os.path.join(beta_dir, "siginfo_beta.txt")
        beta_gctx_path = os.path.join(
            beta_dir, "level5_beta_trt_cp_n720216x12328.gctx"
        )
        if not (os.path.exists(beta_siginfo_path) and os.path.exists(beta_gctx_path)):
            print(f"\n[verify] [WARN] beta 文件缺失，跳过 beta 对照: {beta_dir}")
        else:
            print("\n[verify] 与 LINCS2020 beta Level5 比较（不同数据集，仅趋势参考）：")
            beta_si = pd.read_csv(
                beta_siginfo_path, sep="\t",
                usecols=["sig_id", "pert_type", "cmap_name"],
                dtype=str, low_memory=False,
            )
            beta_map = _drug_to_sigs(beta_si, "cmap_name", "sig_id", "trt_cp")
            b_cols, b_rows, b_shape = _gctx_meta(h5py, beta_gctx_path)
            b_col_pos = {s: i for i, s in enumerate(b_cols)}
            b_row_pos = {g: i for i, g in enumerate(b_rows)}
            b_missing = [g for g in gene_ids if g not in b_row_pos]
            if b_missing:
                print(f"  [WARN] {len(b_missing)} 个 landmark 基因不在 beta GCTX 中，跳过")
            else:
                b_gene_pos = [b_row_pos[g] for g in gene_ids]
                for name in candidates:
                    if name not in beta_map:
                        continue
                    truth, used = _median_from_gctx(
                        h5py, beta_gctx_path, beta_map[name], b_col_pos,
                        b_gene_pos, args.max_sigs_per_drug, rng,
                    )
                    if truth is None:
                        continue
                    idx = names.index(name)
                    r = _pearson(cache[:, idx], truth)
                    print(f"  - {name}: r={r:.4f}  (使用 {used} 个 beta signature)")

    if not finite:
        sys.exit("[verify] 没有得到任何可用的相关系数，请检查输入数据")

    bad = [r for r in finite if r < args.min_corr]
    if bad:
        print(f"\n[verify] [FAIL] {len(bad)} 个药物低于阈值 {args.min_corr}；缓存不可信。")
        sys.exit(1)
    print(f"\n[verify] [OK] 全部药物 r >= {args.min_corr}，缓存与 GCTX 真值一致。")


if __name__ == "__main__":
    main()

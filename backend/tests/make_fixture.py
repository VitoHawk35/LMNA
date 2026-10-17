#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重建 LMNA 测试夹具（LINCS2020 beta Level5）。

数据源（keji 服务器，只读）：
    /data2/wanggang/camp/level5/siginfo_beta.txt
    /data2/wanggang/camp/level5/GSE92742_Broad_LINCS_gene_info.txt.gz
    /data2/wanggang/camp/level5/level5_beta_trt_sh_n238351x12328.gctx
    /data2/wanggang/camp/level5/level5_beta_trt_cp_n720216x12328.gctx
    化合物靶点注释：Drug Repurposing Hub（脚本内下载，约 0.5MB）

在服务器上运行（不需要写服务器文件）：

    source ~/miniconda3/etc/profile.d/conda.sh && conda activate cmap
    python make_fixture.py --stdout-tar > lmna_fixture.tar

或写到指定目录：

    python make_fixture.py --out-dir /path/to/fixture

为什么不用 GSE92742 的 fast_matrix.npy：
    cmap_data/col_sig_ids.csv 是排序后的 sig_id，与 fast_matrix.npy 的列顺序
    （= GCTX 的 COL 顺序）不一致；用它取列会取到错误签名。实测 GSE92742 的
    trt_sh 自身敲低信号也很弱。level5_beta_* 的样本数与任务参考表完全吻合
    （CDK4 86、TOP2A 96，EGFR/MTOR 各取前 150），因此以 beta 数据重建。

生成：
    lmna_fixture.npz       gene_symbols(978), sh_matrix(978 x n_sh), cp_matrix(978 x n_cp)
    lmna_fixture_sh.tsv    sig_id, pert_id, pert_iname, cell_id, pert_type
    lmna_fixture_cp.tsv    同列（药物级中位数签名）
    lmna_fixture_meta.json 每个靶点的已知抑制剂名单
"""

import argparse
import io
import json
import os
import sys
import tarfile
import urllib.request

import h5py
import numpy as np
import pandas as pd

TARGETS = ("CDK4", "TOP2A", "EGFR", "MTOR")
REPURPOSING_URL = (
    "https://s3.amazonaws.com/data.clue.io/repurposing/downloads/"
    "repurposing_drugs_20200324.txt"
)
SIG_COLUMNS = ["sig_id", "pert_id", "pert_iname", "cell_id", "pert_type"]


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def _gctx_col_ids(path):
    with h5py.File(path, "r") as f:
        ids = [
            x.decode() if isinstance(x, bytes) else str(x)
            for x in f["0/META/COL/id"][:]
        ]
    return ids


def _gctx_row_ids(path):
    with h5py.File(path, "r") as f:
        ids = [
            x.decode() if isinstance(x, bytes) else str(x)
            for x in f["0/META/ROW/id"][:]
        ]
    return ids


def _load_landmark_rows(level5_dir, sh_gctx):
    gene_info = pd.read_csv(
        os.path.join(level5_dir, "GSE92742_Broad_LINCS_gene_info.txt.gz"),
        sep="\t",
    )
    lm = gene_info[gene_info["pr_is_lm"] == 1].copy()
    row_ids = _gctx_row_ids(sh_gctx)
    row_pos = {gid: i for i, gid in enumerate(row_ids)}

    ids = lm["pr_gene_id"].astype(str).tolist()
    missing = [gid for gid in ids if gid not in row_pos]
    if missing:
        raise RuntimeError(f"{len(missing)} 个 landmark 基因不在 GCTX ROW 中")

    rows = np.array([row_pos[gid] for gid in ids], dtype=np.int64)
    symbols = [str(s) for s in lm["pr_gene_symbol"].tolist()]
    return rows, symbols


def _load_siginfo(level5_dir):
    return pd.read_csv(
        os.path.join(level5_dir, "siginfo_beta.txt"),
        sep="\t",
        usecols=["sig_id", "pert_id", "pert_type", "cmap_name", "cell_iname"],
        dtype={
            "sig_id": str, "pert_id": str, "pert_type": str,
            "cmap_name": str, "cell_iname": str,
        },
        low_memory=False,
    )


def _select_shrna(siginfo, max_target_samples, n_null, seed):
    sh = siginfo[siginfo["pert_type"] == "trt_sh"].copy()
    sh["_gene_upper"] = sh["cmap_name"].fillna("").str.upper()
    sh = sh.drop_duplicates("sig_id")

    target_frames = []
    for gene in TARGETS:
        # 保持 siginfo 原始顺序取前 N 个（与参考实现的样本数/覆盖度一致）
        sub = sh[sh["_gene_upper"] == gene].head(max_target_samples)
        log(f"[fixture] {gene}: {len(sub)} 个 trt_sh 签名, "
            f"{sub['pert_id'].nunique()} 个 hairpin")
        if len(sub) == 0:
            raise RuntimeError(f"{gene} 在 beta 数据中没有 trt_sh 签名")
        target_frames.append(sub)

    targets_df = pd.concat(target_frames, ignore_index=True)
    used = set(targets_df["sig_id"])

    candidates = sh[~sh["_gene_upper"].isin(TARGETS)].copy()
    candidates = candidates[~candidates["sig_id"].isin(used)]
    candidates = candidates.sort_values("sig_id").reset_index(drop=True)
    if len(candidates) < n_null:
        raise RuntimeError(f"可选 null 池不足: {len(candidates)} < {n_null}")

    rng = np.random.default_rng(seed)
    chosen_idx = np.sort(rng.choice(len(candidates), size=n_null, replace=False))
    null_df = candidates.iloc[chosen_idx]

    sh_df = pd.concat([targets_df, null_df], ignore_index=True)
    sh_df = sh_df.drop_duplicates("sig_id").reset_index(drop=True)

    # 输出列名与 IDataProvider 约定一致
    sh_df = pd.DataFrame({
        "sig_id": sh_df["sig_id"].values,
        "pert_id": sh_df["pert_id"].values,
        "pert_iname": sh_df["_gene_upper"].values,
        "cell_id": sh_df["cell_iname"].values,
        "pert_type": "trt_sh",
    })
    log(f"[fixture] shRNA: 4 靶点 + {n_null} null = {len(sh_df)} 列")
    return sh_df


def _read_gctx_rows(path, col_ids, sig_ids, landmark_rows, chunk_size=20000):
    """读取 GCTX 中指定签名 × landmark 基因，返回 (n_sig, 978)。"""
    col_pos = {sid: i for i, sid in enumerate(col_ids)}
    missing = [sid for sid in sig_ids if sid not in col_pos]
    if missing:
        raise RuntimeError(f"{len(missing)} 个 sig_id 不在 GCTX COL 中")

    indices = np.array([col_pos[sid] for sid in sig_ids], dtype=np.int64)
    out = np.empty((len(indices), len(landmark_rows)), dtype=np.float32)

    with h5py.File(path, "r") as f:
        dataset = f["0/DATA/0/matrix"]
        for start in range(0, len(indices), chunk_size):
            end = min(start + chunk_size, len(indices))
            original = indices[start:end]
            sorted_idx = np.sort(original)
            # h5py 只允许一个 fancy index；先取行，再在内存中切 landmark 列
            block = dataset[sorted_idx][:, landmark_rows]
            if not np.array_equal(sorted_idx, original):
                # 恢复到传入 sig_ids 的顺序
                block = block[np.searchsorted(sorted_idx, original)]
            out[start:end] = block.astype(np.float32, copy=False)
            log(f"[fixture] 读取 {os.path.basename(path)}: {end}/{len(indices)}")
    return out


def _download_repurposing(path):
    if path:
        with open(path, "rb") as f:
            raw = f.read()
    else:
        log("[fixture] 下载 Drug Repurposing Hub 注释...")
        with urllib.request.urlopen(REPURPOSING_URL, timeout=60) as resp:
            raw = resp.read()
    text = raw.decode("utf-8", "replace")
    df = pd.read_csv(io.StringIO(text), sep="\t", comment="!", dtype=str)
    needed = {"pert_iname", "target"}
    if not needed.issubset(df.columns):
        raise RuntimeError(f"Repurposing 注释缺少列: {sorted(needed - set(df.columns))}")
    return df


def _select_compounds(siginfo, repurposing):
    cp = siginfo[siginfo["pert_type"] == "trt_cp"].copy()
    cp = cp[cp["cmap_name"].notna()]
    cp_names = set(cp["cmap_name"].astype(str))
    lower_to_actual = {name.lower(): name for name in cp_names}

    # Repurposing Hub 全表与 CMAP 化合物名的交集（约 3155 个，接近参考的 3161）
    rep_names = repurposing["pert_iname"].dropna().astype(str).tolist()
    selected = sorted({
        lower_to_actual[name.lower()]
        for name in rep_names
        if name.lower() in lower_to_actual
    })
    if not selected:
        raise RuntimeError("Repurposing Hub 与 CMAP 化合物没有交集")

    # 每个靶点的已知抑制剂：Repurposing 的 target 字段包含该基因
    inhibitors = {}
    for gene in TARGETS:
        mask = repurposing["target"].fillna("").str.upper().str.split("|").apply(
            lambda xs: gene in xs
        )
        names = []
        for name in repurposing.loc[mask, "pert_iname"].dropna().astype(str):
            actual = lower_to_actual.get(name.lower())
            if actual is not None:
                names.append(actual)
        inhibitors[gene] = sorted(set(names))
        log(f"[fixture] {gene} 已知抑制剂: {len(inhibitors[gene])} 个")

    log(f"[fixture] 化合物: {len(selected)} 个")
    return cp[cp["cmap_name"].isin(selected)].copy(), selected, inhibitors


def _build_cp_matrix(level5_dir, cp_siginfo, selected_names, landmark_rows,
                     cp_col_ids, cp_gctx):
    name_to_sigs = {}
    for sid, name in zip(cp_siginfo["sig_id"], cp_siginfo["cmap_name"]):
        name_to_sigs.setdefault(name, []).append(sid)

    col_pos = {sid: i for i, sid in enumerate(cp_col_ids)}
    out = np.empty((len(landmark_rows), len(selected_names)), dtype=np.float32)

    # 按药物分批读取，避免把 43 万条签名一次全部载入内存
    BATCH_DRUGS = 50
    with h5py.File(cp_gctx, "r") as f:
        dataset = f["0/DATA/0/matrix"]
        for start in range(0, len(selected_names), BATCH_DRUGS):
            batch = selected_names[start:start + BATCH_DRUGS]
            pairs = []
            for name in batch:
                for sid in name_to_sigs.get(name, []):
                    if sid in col_pos:
                        pairs.append((col_pos[sid], name))
            if not pairs:
                continue
            pairs.sort()
            indices = np.array([p[0] for p in pairs], dtype=np.int64)
            names_sorted = [p[1] for p in pairs]
            block = dataset[indices][:, landmark_rows].astype(np.float32, copy=False)

            names_arr = np.array(names_sorted)
            for j, name in enumerate(batch):
                rows_here = np.flatnonzero(names_arr == name)
                if len(rows_here) == 0:
                    raise RuntimeError(f"化合物 {name} 没有可用签名")
                out[:, start + j] = np.median(block[rows_here, :], axis=0)
            log(f"[fixture] 药物中位数: "
                f"{start + len(batch)}/{len(selected_names)}")
    return out


def _build_meta(symbols, sh_df, selected_names, inhibitors):
    targets = {}
    for gene in TARGETS:
        sub = sh_df[sh_df["pert_iname"] == gene]
        targets[gene] = {
            "inhibitors": inhibitors.get(gene, []),
            "n_shrna_samples": int(len(sub)),
            "n_hairpins": int(sub["pert_id"].nunique()),
        }
    return {
        "source": "LINCS2020 beta Level5 (level5_beta_trt_sh/trt_cp)",
        "generated_by": "backend/tests/make_fixture.py",
        "seed": 42,
        "n_genes": len(symbols),
        "n_sh": int(len(sh_df)),
        "n_cp": int(len(selected_names)),
        "targets": targets,
        "inhibitors": {g: info["inhibitors"] for g, info in targets.items()},
    }


def build_fixture(level5_dir, max_target_samples, n_null, seed,
                  repurposing_file=None):
    sh_gctx = os.path.join(level5_dir, "level5_beta_trt_sh_n238351x12328.gctx")
    cp_gctx = os.path.join(level5_dir, "level5_beta_trt_cp_n720216x12328.gctx")

    landmark_rows, symbols = _load_landmark_rows(level5_dir, sh_gctx)
    if len(symbols) != 978:
        raise RuntimeError(f"landmark 基因数不是 978: {len(symbols)}")

    siginfo = _load_siginfo(level5_dir)
    sh_df = _select_shrna(siginfo, max_target_samples, n_null, seed)

    sh_col_ids = _gctx_col_ids(sh_gctx)
    sh_block = _read_gctx_rows(
        sh_gctx, sh_col_ids, sh_df["sig_id"].tolist(), landmark_rows
    )
    sh_matrix = sh_block.T.copy()

    repurposing = _download_repurposing(repurposing_file)
    cp_siginfo, selected_names, inhibitors = _select_compounds(
        siginfo, repurposing
    )
    cp_col_ids = _gctx_col_ids(cp_gctx)
    cp_matrix = _build_cp_matrix(
        level5_dir, cp_siginfo, selected_names, landmark_rows,
        cp_col_ids, cp_gctx,
    )

    cp_df = pd.DataFrame({
        "sig_id": [f"CP::{name}" for name in selected_names],
        "pert_id": [f"CP::{name}" for name in selected_names],
        "pert_iname": selected_names,
        "cell_id": ["MULTI"] * len(selected_names),
        "pert_type": ["trt_cp"] * len(selected_names),
    })

    meta = _build_meta(symbols, sh_df, selected_names, inhibitors)

    npz_buf = io.BytesIO()
    np.savez_compressed(
        npz_buf,
        gene_symbols=np.array(symbols),
        sh_matrix=sh_matrix,
        cp_matrix=cp_matrix,
    )

    files = {
        "lmna_fixture.npz": npz_buf.getvalue(),
        "lmna_fixture_sh.tsv": sh_df.to_csv(sep="\t", index=False).encode("utf-8"),
        "lmna_fixture_cp.tsv": cp_df.to_csv(sep="\t", index=False).encode("utf-8"),
        "lmna_fixture_meta.json": json.dumps(
            meta, ensure_ascii=False, indent=2
        ).encode("utf-8"),
    }
    return files, meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--level5-dir", default="/data2/wanggang/camp/level5"
    )
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--stdout-tar", action="store_true")
    parser.add_argument("--repurposing-file", default=None,
                        help="本地 Repurposing Hub TSV（缺省时从网络下载）")
    parser.add_argument("--max-target-samples", type=int, default=150)
    parser.add_argument("--n-null", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    files, meta = build_fixture(
        args.level5_dir,
        max_target_samples=args.max_target_samples,
        n_null=args.n_null,
        seed=args.seed,
        repurposing_file=args.repurposing_file,
    )

    if args.stdout_tar:
        tar = tarfile.open(fileobj=sys.stdout.buffer, mode="w|")
        for name, content in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        tar.close()
        sys.stdout.buffer.flush()
    elif args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        for name, content in files.items():
            with open(os.path.join(args.out_dir, name), "wb") as f:
                f.write(content)
        log(f"[fixture] 已写入 {args.out_dir}")
    else:
        parser.error("需要 --out-dir 或 --stdout-tar")

    log("[fixture] 完成: " + json.dumps(meta["targets"], ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7e 阶段 1 · 任务 2（+任务 5 实测）：提取 5 个基因的 trt_sh 实例 + 同板 ctl_vector
+ 2,000 实例随机背景池，按任务卡默认口径算 robust z：

    z = (x − median(同板 ctl_vector)) / (MAD × 1.4826)

回退级别（写入元数据 fallback_level）：
    0 = 同板 ctl_vector（≥3 孔）
    1 = 同细胞系 ctl_vector（提取池内，≥3 孔）
    2 = 全局 ctl_vector（提取池内全部）
MAD=0/NaN → 该基因该实例置 NaN 并计数。

产物（不提交 git，仅服务器 /home/keji/l3_tmp/）：
    data/spike_z.npz        z_target, z_bg, 元数据
    results/02_extract.json 计数、回退/NaN 统计、吞吐实测（供全量估算）
"""
import json
import os
import sys
import time

import h5py
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (P1_L3_GCTX, P1_INST_INFO, GENE_INFO, GENES, N_BACKGROUND,
                    MIN_CTL_PER_PLATE, EPS_SCALE, READ_CHUNK, RANDOM_SEED,
                    OUT_DATA, OUT_RESULTS)

t0 = time.time()


def log(msg):
    print(f"[{time.time()-t0:7.1f}s] {msg}", flush=True)


stats = {"script": "02_extract_z"}

# ============ 1. 选实例 ============
inst = pd.read_csv(
    P1_INST_INFO, sep="\t", dtype=str, low_memory=False,
    usecols=["inst_id", "rna_plate", "rna_well", "pert_id", "pert_iname",
             "pert_type", "cell_id"],
)
sh = inst[inst["pert_type"] == "trt_sh"].copy()   # 精确匹配，禁止 startswith
target_mask = sh["pert_iname"].str.upper().isin(GENES)
target = sh[target_mask].copy()
rest = sh[~target_mask]
rng = np.random.default_rng(RANDOM_SEED)
bg_pos = rng.choice(len(rest), N_BACKGROUND, replace=False)
bg = rest.iloc[np.sort(bg_pos)].copy()
log(f"目标实例 {len(target)}，背景池 {len(bg)}")

needed_plates = set(target["rna_plate"]) | set(bg["rna_plate"])
ctl = inst[(inst["pert_type"] == "ctl_vector") &
           (inst["rna_plate"].isin(needed_plates))].copy()
stats["n_target"] = int(len(target))
stats["n_background"] = int(len(bg))
stats["n_needed_plates"] = int(len(needed_plates))
stats["n_ctl_on_needed_plates"] = int(len(ctl))
log(f"涉及板 {len(needed_plates)}，板上 ctl_vector {len(ctl)}")

# ============ 2. gctx 行列映射（ID 一律取 gctx 内部 META） ============
gene_info = pd.read_csv(GENE_INFO, sep="\t", low_memory=False)
lm = gene_info[gene_info["pr_is_lm"] == 1]
lm_ids = lm["pr_gene_id"].astype(str).tolist()
lm_symbols = lm["pr_gene_symbol"].astype(str).tolist()

with h5py.File(P1_L3_GCTX, "r") as f:
    col_ids = [x.decode() for x in f["0/META/COL/id"][:]]
    row_ids = [x.decode() for x in f["0/META/ROW/id"][:]]
col_map = {c: i for i, c in enumerate(col_ids)}
row_map = {r: i for i, r in enumerate(row_ids)}
lm_rows = np.array([row_map[g] for g in lm_ids], dtype=np.int64)
del row_ids
log(f"列 {len(col_map)}，landmark 行 {len(lm_rows)}")


def read_rows(inst_ids, mat_path, tag):
    """按 inst_id 列表读 (n, 978) float32；返回 (data, 缺失列表, 秒)。"""
    missing = [g for g in inst_ids if g not in col_map]
    ids = [g for g in inst_ids if g in col_map]
    idx = np.array([col_map[g] for g in ids], dtype=np.int64)
    order = np.argsort(idx)
    idx_sorted = idx[order]
    out = np.empty((len(ids), 978), dtype=np.float32)
    t = time.time()
    with h5py.File(mat_path, "r") as f:
        mat = f["0/DATA/0/matrix"]
        for s in range(0, len(ids), READ_CHUNK):
            e = min(s + READ_CHUNK, len(ids))
            out[order[s:e]] = mat[idx_sorted[s:e], :][:, lm_rows]
    dt = time.time() - t
    log(f"{tag}: 读 {len(ids)} 行用 {dt:.1f}s（{len(ids)/max(dt,1e-9):.0f} 行/s），缺失 {len(missing)}")
    return out, missing, dt, ids


# ============ 3. 读 ctl + 样本 ============
ctl_data, ctl_missing, ctl_sec, ctl_ids = read_rows(
    ctl["inst_id"].tolist(), P1_L3_GCTX, "ctl_vector")
ctl = ctl[ctl["inst_id"].isin(set(ctl_ids))].reset_index(drop=True)

sample = pd.concat([target, bg], ignore_index=True)
X, smpl_missing, smpl_sec, smpl_ids = read_rows(
    sample["inst_id"].tolist(), P1_L3_GCTX, "target+background")
sample = sample[sample["inst_id"].isin(set(smpl_ids))].reset_index(drop=True)

stats["missing_in_gctx"] = {"ctl": ctl_missing, "sample": smpl_missing}
stats["throughput"] = {
    "ctl_rows": len(ctl_ids), "ctl_seconds": round(ctl_sec, 2),
    "sample_rows": len(smpl_ids), "sample_seconds": round(smpl_sec, 2),
    "rows_per_s_overall": round((len(ctl_ids) + len(smpl_ids)) /
                                max(ctl_sec + smpl_sec, 1e-9), 1),
}

# ============ 4. robust z（三级回退） ============
ctl_cell = ctl["cell_id"].values
ctl_plate = ctl["rna_plate"].values

plate_stats = {}
for pl in np.unique(ctl_plate):
    vals = ctl_data[ctl_plate == pl]
    n = vals.shape[0]
    med = np.median(vals, axis=0)
    mad = np.median(np.abs(vals - med), axis=0)
    plate_stats[pl] = (med.astype(np.float32), (1.4826 * mad).astype(np.float32), n)

cell_stats = {}
for cl in np.unique(ctl_cell):
    vals = ctl_data[ctl_cell == cl]
    med_c = np.median(vals, axis=0).astype(np.float32)
    scale_c = (1.4826 * np.median(np.abs(vals - med_c), axis=0)).astype(np.float32)
    cell_stats[cl] = (med_c, scale_c, vals.shape[0])

g_med = np.median(ctl_data, axis=0).astype(np.float32)
g_mad = (1.4826 * np.median(np.abs(ctl_data - g_med), axis=0)).astype(np.float32)
log(f"板级统计 {len(plate_stats)} 板，细胞系 {len(cell_stats)} 个，全局统计完成")

Z = np.empty_like(X)
levels = np.empty(len(sample), dtype=np.int8)
nan_gene_hits = np.zeros(978, dtype=np.int64)   # 逐基因 NaN 计数
nan_instances = 0
level_counts = {0: 0, 1: 0, 2: 0}
inst_on_lt3_plate = 0

smpl_plates = sample["rna_plate"].values
smpl_cells = sample["cell_id"].values
for i in range(len(sample)):
    pl, cl = smpl_plates[i], smpl_cells[i]
    st = plate_stats.get(pl)
    if st is not None and st[2] >= MIN_CTL_PER_PLATE:
        med, scale, lvl = st[0], st[1], 0
    else:
        inst_on_lt3_plate += 1
        cs = cell_stats.get(cl)
        if cs is not None and cs[2] >= MIN_CTL_PER_PLATE:
            med, scale, lvl = cs[0], cs[1], 1
        else:
            med, scale, lvl = g_med, g_mad, 2
    bad = (~np.isfinite(scale)) | (scale <= EPS_SCALE) | (~np.isfinite(med))
    z = (X[i] - med) / np.where(bad, 1.0, scale)
    if bad.any():
        z[bad] = np.nan
        nan_gene_hits += bad.astype(np.int64)
        nan_instances += 1
    Z[i] = z.astype(np.float32)
    levels[i] = lvl
    level_counts[lvl] += 1

log(f"robust z 完成：回退分布 {level_counts}，含 NaN 实例 {nan_instances}")

sample["fallback_level"] = levels
is_target = sample["pert_iname"].str.upper().isin(GENES).values
stats["fallback_counts"] = {str(k): int(v) for k, v in level_counts.items()}
stats["instances_on_lt3_plate"] = int(inst_on_lt3_plate)
stats["nan_instances"] = int(nan_instances)
stats["nan_gene_hits_total"] = int(nan_gene_hits.sum())
stats["nan_gene_hits_top10"] = {
    lm_symbols[i]: int(nan_gene_hits[i])
    for i in np.argsort(-nan_gene_hits)[:10] if nan_gene_hits[i] > 0
}
stats["elapsed_s"] = round(time.time() - t0, 1)

# ============ 5. 落盘 ============
os.makedirs(OUT_DATA, exist_ok=True)
os.makedirs(OUT_RESULTS, exist_ok=True)
np.savez_compressed(
    os.path.join(OUT_DATA, "spike_z.npz"),
    Z=Z, is_target=is_target,
    inst_id=sample["inst_id"].values.astype("U64"),
    pert_iname=sample["pert_iname"].values.astype("U32"),
    pert_id=sample["pert_id"].values.astype("U32"),
    cell_id=sample["cell_id"].values.astype("U16"),
    rna_plate=sample["rna_plate"].values.astype("U64"),
    fallback_level=levels,
    lm_symbols=np.array(lm_symbols, dtype="U32"),
)
out = os.path.join(OUT_RESULTS, "02_extract.json")
with open(out, "w", encoding="utf-8") as fp:
    json.dump(stats, fp, ensure_ascii=False, indent=2)
log(f"写出 {out}；总耗时 {(time.time()-t0)/60:.1f} 分钟")

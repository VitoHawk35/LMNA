#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7e 阶段 1 · 任务 1：gctx 布局确认 + 读速基准 + inst_info 计数。

输出：/home/keji/l3_tmp/results/01_probe.json
只读服务器数据，不写任何生产目录。
"""
import json
import os
import sys
import time

import h5py
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (P1_L3_GCTX, P1_INST_INFO, GENE_INFO, GENES,
                    OUT_RESULTS, RANDOM_SEED)

t0 = time.time()
result = {"script": "01_probe_layout", "gctx": P1_L3_GCTX}

# ---------- 1a. HDF5 布局 ----------
with h5py.File(P1_L3_GCTX, "r") as f:
    layout = []

    def _walk(name, obj):
        if isinstance(obj, h5py.Dataset):
            layout.append({
                "path": name, "shape": list(obj.shape), "dtype": str(obj.dtype),
                "chunks": obj.chunks, "compression": obj.compression,
            })
        else:
            layout.append({"path": name, "type": "group"})
    f.visititems(_walk)
    result["layout"] = layout

    m = f["0/DATA/0/matrix"]
    result["matrix_shape"] = list(m.shape)   # (n_instances, n_genes)：行=实例，列=基因
    result["matrix_dtype"] = str(m.dtype)
    result["file_bytes"] = os.path.getsize(P1_L3_GCTX)

    row_ids = [x.decode() for x in f["0/META/ROW/id"][:]]
    col_ids_head = [x.decode() for x in f["0/META/COL/id"][:3]]
    result["row_id_first3"] = row_ids[:3]
    result["col_id_first3"] = col_ids_head
    result["n_row_ids"] = len(row_ids)

    # ---------- 1b. 读速基准 ----------
    rng = np.random.default_rng(RANDOM_SEED)
    # 散布随机 400 行（冷路径，seek 密集）
    cols = np.sort(rng.choice(m.shape[0], 400, replace=False))
    t = time.time()
    block = m[cols, :]
    t_scatter = time.time() - t
    lm_rows_demo = np.arange(0, m.shape[1], 12)[:978]
    t = time.time()
    _ = block[:, lm_rows_demo]
    t_subset = time.time() - t
    # 连续 400 行（热路径）
    t = time.time()
    _ = m[100000:100400, :]
    t_contig = time.time() - t
    # 2 万行排序块（模拟正式提取的读取模式）
    cols2 = np.sort(rng.choice(m.shape[0], 20000, replace=False))
    t = time.time()
    _ = m[cols2, :]
    t_chunk20k = time.time() - t

result["benchmark"] = {
    "scatter_400_rows_s": round(t_scatter, 3),
    "subset_978_cols_s": round(t_subset, 4),
    "contig_400_rows_s": round(t_contig, 3),
    "sorted_20000_rows_s": round(t_chunk20k, 3),
    "sorted_20000_rows_per_s": round(20000 / t_chunk20k, 1),
}
print(f"[{time.time()-t0:6.1f}s] gctx 布局+基准完成", flush=True)

# ---------- 1c. inst_info 计数 ----------
inst = pd.read_csv(
    P1_INST_INFO, sep="\t", dtype=str, low_memory=False,
    usecols=["inst_id", "rna_plate", "rna_well", "pert_id", "pert_iname",
             "pert_type", "cell_id", "pert_time"],
)
result["inst_info_rows"] = len(inst)
pt = inst["pert_type"].value_counts()
result["pert_type_counts"] = {k: int(v) for k, v in pt.items()}
n_exact = int((inst["pert_type"] == "trt_sh").sum())
n_prefix = int(inst["pert_type"].str.startswith("trt_sh").sum())
result["trt_sh_exact"] = n_exact
result["trt_sh_startswith"] = n_prefix   # 含 .cgs/.css，禁止使用的口径

sh = inst[inst["pert_type"] == "trt_sh"]
per_gene = {}
for g in GENES:
    sub = sh[sh["pert_iname"].str.upper() == g]
    per_gene[g] = {
        "n_instances": int(len(sub)),
        "n_hairpins": int(sub["pert_id"].nunique()),
        "n_cells": int(sub["cell_id"].nunique()),
        "n_plates": int(sub["rna_plate"].nunique()),
    }
result["per_gene_trt_sh"] = per_gene

# LMNA 明细（论文 84 实例的对照）
lmna = sh[sh["pert_iname"].str.upper() == "LMNA"]
result["lmna_by_cell"] = {k: int(v) for k, v in
                          lmna["cell_id"].value_counts().head(15).items()}
result["lmna_by_time"] = {k: int(v) for k, v in
                          lmna["pert_time"].value_counts().items()}

# ctl_vector 总量与 shRNA 板覆盖
ctl = inst[inst["pert_type"] == "ctl_vector"]
sh_plates = set(sh["rna_plate"].unique())
ctl_on_sh_plates = ctl[ctl["rna_plate"].isin(sh_plates)]
per_plate = ctl_on_sh_plates.groupby("rna_plate").size()
result["ctl_vector_total"] = int(len(ctl))
result["ctl_vector_on_shrna_plates"] = int(len(ctl_on_sh_plates))
result["shrna_plates"] = int(len(sh_plates))
result["shrna_plates_with_ctl"] = int(per_plate.size)
result["ctl_per_plate_quantiles"] = {
    "min": int(per_plate.min()), "p25": float(per_plate.quantile(0.25)),
    "median": float(per_plate.median()), "p75": float(per_plate.quantile(0.75)),
    "max": int(per_plate.max()),
}
result["plates_ctl_lt3"] = int((per_plate < 3).sum())

# landmark 行映射自检（978 行是否都能在 gctx ROW id 中找到）
gene_info = pd.read_csv(GENE_INFO, sep="\t", low_memory=False)
lm = gene_info[gene_info["pr_is_lm"] == 1]
lm_ids = lm["pr_gene_id"].astype(str).tolist()
row_set = set(row_ids)
result["landmark_n"] = len(lm_ids)
result["landmark_missing_in_gctx"] = [g for g in lm_ids if g not in row_set]
sym = dict(zip(gene_info["pr_gene_id"].astype(str), gene_info["pr_gene_symbol"]))
result["five_genes_landmark"] = {
    g: bool(((gene_info["pr_gene_symbol"].str.upper() == g) &
             (gene_info["pr_is_lm"] == 1)).any()) for g in GENES
}

os.makedirs(OUT_RESULTS, exist_ok=True)
out = os.path.join(OUT_RESULTS, "01_probe.json")
with open(out, "w", encoding="utf-8") as fp:
    json.dump(result, fp, ensure_ascii=False, indent=2)
print(f"[{time.time()-t0:6.1f}s] 写出 {out}", flush=True)

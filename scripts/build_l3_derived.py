#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7e 阶段 2 · 任务 1：L3 派生层全量构建（顺序流式扫描 65 GB gctx）

口径（用户批准，docs/design/L7e-spike-report.md §7 + 任务卡）：
    z = (x − median(同板 ctl_vector)) / scale
    scale = max(1.4826 × MAD, 同板 scale 中位数 × 0.01)   # scale-floor 防爆
    MAD=0 → 该基因在该板置 NaN（签名计算前剔除，计数入 QC/manifest）
    对照只用 ctl_vector；同板 <3 孔 → 同细胞系（提取池内）→ 全局（fallback_level）
    pert_type == 'trt_sh' 精确匹配；行/列 ID 从 gctx 内部 0/META/ROW|COL/id 读
    聚合：实例级（每孔一个样本）

产物（L3_DERIVED_DIR，默认 /home/keji/l3_tmp/derived/l3_v1；服务器红线：
写入仅限 /home/keji/l3_tmp/）：
    l3_landmark.npy    (n_instances, 978) float32 robust z（含 NaN）
    instance_meta.csv  inst_id, rna_plate, pert_id, pert_iname, cell_id,
                       pert_type, n_controls, fallback_level
    col_ids.txt        矩阵行 ID 花名册（inst_id，与 npy 行一一对应）
    row_genes.csv      矩阵列花名册（entrez_id, gene_symbol，978 行）
    manifest.json      源文件路径/大小/sha256、行列 ID sha256、参数、
                       代码提交号、耗时、QC 计数

服务器运行：
    ~/miniconda3/envs/cmap/bin/python -B build_l3_derived.py
环境变量：
    L3_GCTX_PATH / L3_INST_INFO_PATH / L3_GENE_INFO_PATH  数据源覆盖
    L3_DERIVED_DIR   输出目录（默认 /home/keji/l3_tmp/derived/l3_v1）
    L3_READ_CHUNK    gctx 扫描块行数（默认 20000）
    CODE_COMMIT      代码提交号（缺省尝试 git rev-parse HEAD）
    L3_SKIP_SOURCE_SHA256=1  跳过 65 GB 源文件 sha256（调试用，交付勿用）
"""

import hashlib
import json
import os
import subprocess
import sys
import time

import h5py
import numpy as np
import pandas as pd

# 复用 backend 的纯函数口径（脚本从仓库根/backend 均可运行）
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "backend")
if os.path.isdir(_BACKEND_DIR):
    sys.path.insert(0, _BACKEND_DIR)
from l3_robust_z import (  # noqa: E402
    MIN_CTL_PER_PLATE, EPS_SCALE, SCALE_FLOOR_REL, MAD_TO_SD,
    plate_robust_stats, resolve_control_stats, apply_robust_z,
)

# ---------------- 路径（env 可配） ----------------
L3_GCTX = os.getenv(
    "L3_GCTX_PATH",
    "/data2/wanggang/camp/level3/"
    "GSE92742_Broad_LINCS_Level3_INF_mlr12k_n1319138x12328.gctx",
)
INST_INFO = os.getenv(
    "L3_INST_INFO_PATH",
    "/data2/wanggang/camp/level3/GSE92742_Broad_LINCS_inst_info.txt",
)
GENE_INFO = os.getenv(
    "L3_GENE_INFO_PATH",
    "/home/keji/cmap_v2_data/GSE92742_Broad_LINCS_gene_info.txt.gz",
)
OUT_DIR = os.getenv("L3_DERIVED_DIR", "/home/keji/l3_tmp/derived/l3_v1")
READ_CHUNK = int(os.getenv("L3_READ_CHUNK", "20000"))

t0 = time.time()


def log(msg):
    print(f"[{time.time()-t0:8.1f}s] {msg}", flush=True)


def sha256_file(path, chunk=1 << 26):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sha256_lines(lines):
    """行 ID 花名册的稳定指纹：逐行 utf-8 + \\n 拼接后 sha256。"""
    h = hashlib.sha256()
    for line in lines:
        h.update(str(line).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def code_commit():
    env = os.getenv("CODE_COMMIT")
    if env:
        return env
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True, text=True, timeout=15,
        ).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# ============ 1. inst_info 选实例（trt_sh 精确匹配 + 同板 ctl_vector） ============
log("读 inst_info ...")
inst = pd.read_csv(
    INST_INFO, sep="\t", dtype=str, low_memory=False,
    usecols=["inst_id", "rna_plate", "pert_id", "pert_iname",
             "pert_type", "cell_id"],
)
shrna = inst[inst["pert_type"] == "trt_sh"].copy()   # 精确匹配，禁止 startswith
needed_plates = set(shrna["rna_plate"])
ctl = inst[(inst["pert_type"] == "ctl_vector") &
           (inst["rna_plate"].isin(needed_plates))].copy()
meta = pd.concat([shrna, ctl], ignore_index=True)
needed_set = set(meta["inst_id"])
log(f"trt_sh {len(shrna)}，同板 ctl_vector {len(ctl)}，"
    f"板 {len(needed_plates)}，合计行 {len(meta)}")

# ============ 2. gctx 行列映射（ID 一律取 gctx 内部 META） ============
gene_info = pd.read_csv(GENE_INFO, sep="\t", low_memory=False)
lm = gene_info[gene_info["pr_is_lm"] == 1]
lm_entrez = lm["pr_gene_id"].astype(str).tolist()
lm_symbols = lm["pr_gene_symbol"].astype(str).tolist()
assert len(lm_entrez) == 978, f"landmark 基因数 {len(lm_entrez)} != 978"

with h5py.File(L3_GCTX, "r") as f:
    col_ids = [x.decode() for x in f["0/META/COL/id"][:]]
    row_ids = [x.decode() for x in f["0/META/ROW/id"][:]]
    n_rows_total = f["0/DATA/0/matrix"].shape[0]
row_map = {r: i for i, r in enumerate(row_ids)}
missing_lm = [g for g in lm_entrez if g not in row_map]
assert not missing_lm, f"landmark Entrez 不在 gctx ROW/id: {missing_lm[:5]}"
lm_rows = np.array([row_map[g] for g in lm_entrez], dtype=np.int64)
del row_ids, row_map
log(f"gctx 列 {len(col_ids)}，landmark 行 {len(lm_rows)}")

needed_mask = np.array([c in needed_set for c in col_ids], dtype=bool)
n_needed = int(needed_mask.sum())
assert n_needed == len(meta), (
    f"inst_info 选中 {len(meta)} 行，但 gctx COL/id 命中 {n_needed} 行"
)
log(f"gctx 中需提取 {n_needed} / {n_rows_total} 行（{n_needed/n_rows_total:.1%}）")

# ============ 3. 顺序流式全扫描，提取 landmark 列 ============
kept_chunks = []
kept_ids = []
read_bytes = 0
with h5py.File(L3_GCTX, "r") as f:
    mat = f["0/DATA/0/matrix"]
    for r0 in range(0, n_rows_total, READ_CHUNK):
        r1 = min(r0 + READ_CHUNK, n_rows_total)
        mask = needed_mask[r0:r1]
        if not mask.any():
            # 仍需顺序读过以预热页缓存？不需要：跳过的块不读，直接 seek 到
            # 下一块——h5py 按块读，跳块不耗时（连续大文件，页缓存由读取块建立）
            continue
        block = mat[r0:r1, :][:, lm_rows]          # (chunk, 978) float32
        read_bytes += (r1 - r0) * mat.shape[1] * 4
        kept_chunks.append(block[mask])
        kept_ids.extend(
            cid for cid, keep in zip(col_ids[r0:r1], mask) if keep
        )
        if len(kept_chunks) % 10 == 0:
            log(f"扫描 {r1}/{n_rows_total}，已收 "
                f"{sum(c.shape[0] for c in kept_chunks)} 行")
del col_ids, needed_mask
X = np.concatenate(kept_chunks, axis=0)            # (n, 978) float32
del kept_chunks
assert X.shape == (n_needed, 978), f"提取矩阵形状 {X.shape}"
log(f"提取完成 {X.shape}，读放量 {read_bytes/1e9:.1f} GB，"
    f"耗时 {time.time()-t0:.0f}s")

# 元数据按扫描顺序（kept_ids）重排，保证 npy 第 i 行 = meta 第 i 行
meta = meta.set_index("inst_id").loc[kept_ids].reset_index()
assert (meta["inst_id"].values == np.array(kept_ids)).all()
meta["n_controls"] = 0
meta["fallback_level"] = np.int8(-1)

# ============ 4. robust z（scale-floor + MAD=0→NaN + 三级回退） ============
is_ctl = (meta["pert_type"] == "ctl_vector").values
ctl_idx = np.flatnonzero(is_ctl)
ctl_plates = meta["rna_plate"].values[ctl_idx]
ctl_cells = meta["cell_id"].values[ctl_idx]
X_ctl = X[ctl_idx]

log("算板级 ctl 统计 ...")
plate_stats = {}
for pl in np.unique(ctl_plates):
    vals = X_ctl[ctl_plates == pl]
    med, scale, bad = plate_robust_stats(vals)
    plate_stats[pl] = (med, scale, bad, vals.shape[0])

cell_stats = {}
for cl in np.unique(ctl_cells):
    vals = X_ctl[ctl_cells == cl]
    med, scale, bad = plate_robust_stats(vals)
    cell_stats[cl] = (med, scale, bad, vals.shape[0])

g_med, g_scale, g_bad = plate_robust_stats(X_ctl)
global_stats = (g_med, g_scale, g_bad, X_ctl.shape[0])
log(f"板级 {len(plate_stats)} 板，细胞系 {len(cell_stats)} 个，全局完成")

# 每行 n_controls = 该板 ctl_vector 孔数
plate_n_ctl = {pl: st[3] for pl, st in plate_stats.items()}
meta["n_controls"] = meta["rna_plate"].map(plate_n_ctl).fillna(0).astype(int)

log("逐板算 robust z ...")
plates_arr = meta["rna_plate"].values
cells_arr = meta["cell_id"].values
level_counts = {0: 0, 1: 0, 2: 0}
nan_gene_hits = np.zeros(978, dtype=np.int64)
nan_rows = 0

# 按板分组处理（同板同统计量，向量化）
order = np.argsort(plates_arr, kind="stable")
sorted_plates = plates_arr[order]
boundaries = np.flatnonzero(
    np.r_[True, sorted_plates[1:] != sorted_plates[:-1], True]
)
for b in range(len(boundaries) - 1):
    rows = order[boundaries[b]:boundaries[b + 1]]
    pl = sorted_plates[boundaries[b]]
    # 同板内细胞系可能不同（共享板），逐行回退判定但通常整块同级
    # 先按板级判定一次，命中 level 0 则整板向量化
    st = plate_stats.get(pl)
    if st is not None and st[3] >= MIN_CTL_PER_PLATE:
        med, scale, bad, lvl = st[0], st[1], st[2], 0
        X[rows] = apply_robust_z(X[rows], med, scale, bad)
        level_counts[0] += len(rows)
        if bad.any():
            nan_gene_hits += bad.astype(np.int64) * len(rows)
            nan_rows += len(rows)
        meta.loc[rows, "fallback_level"] = np.int8(0)
    else:
        for r in rows:
            med, scale, bad, lvl = resolve_control_stats(
                pl, cells_arr[r], plate_stats, cell_stats, global_stats)
            X[r] = apply_robust_z(X[r], med, scale, bad)
            level_counts[lvl] += 1
            if bad.any():
                nan_gene_hits += bad.astype(np.int64)
                nan_rows += 1
            meta.iat[r, meta.columns.get_loc("fallback_level")] = np.int8(lvl)
log(f"robust z 完成：回退分布 {level_counts}，含 NaN 行 {nan_rows}")

# ctl 行自身相对同板统计量的 z 也已算好（上面按板统一处理），无需特判

# ============ 5. 落盘 ============
os.makedirs(OUT_DIR, exist_ok=True)

npy_path = os.path.join(OUT_DIR, "l3_landmark.npy")
np.save(npy_path, X.astype(np.float32))
log(f"写出 {npy_path}（{os.path.getsize(npy_path)/1e9:.2f} GB）")

meta_path = os.path.join(OUT_DIR, "instance_meta.csv")
meta_out = meta[["inst_id", "rna_plate", "pert_id", "pert_iname",
                 "cell_id", "pert_type", "n_controls", "fallback_level"]]
meta_out.to_csv(meta_path, index=False)

col_ids_path = os.path.join(OUT_DIR, "col_ids.txt")
with open(col_ids_path, "w", encoding="utf-8") as fp:
    fp.write("\n".join(kept_ids) + "\n")

row_genes_path = os.path.join(OUT_DIR, "row_genes.csv")
pd.DataFrame({"entrez_id": lm_entrez, "gene_symbol": lm_symbols}).to_csv(
    row_genes_path, index=False)

# ============ 6. manifest ============
if os.getenv("L3_SKIP_SOURCE_SHA256") == "1":
    gctx_sha = "skipped"
else:
    log("算源 gctx sha256（65 GB，约 1–10 分钟）...")
    gctx_sha = sha256_file(L3_GCTX)
manifest = {
    "derived_version": "l3_v1",
    "created_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
    "code_commit": code_commit(),
    "source": {
        "gctx_path": L3_GCTX,
        "gctx_size": os.path.getsize(L3_GCTX),
        "gctx_sha256": gctx_sha,
        "inst_info_path": INST_INFO,
        "inst_info_size": os.path.getsize(INST_INFO),
        "inst_info_sha256": sha256_file(INST_INFO),
        "gene_info_path": GENE_INFO,
    },
    "matrix": {
        "file": "l3_landmark.npy",
        "shape": [int(X.shape[0]), int(X.shape[1])],
        "dtype": "float32",
        "layout": "行=实例（顺序=col_ids.txt），列=978 landmark（顺序=row_genes.csv）",
        "value": "robust z（MAD=0 基因为 NaN）",
        "col_ids_file": "col_ids.txt",
        "col_ids_sha256": sha256_lines(kept_ids),
        "row_genes_file": "row_genes.csv",
        "row_genes_sha256": sha256_lines(
            [f"{e},{s}" for e, s in zip(lm_entrez, lm_symbols)]),
    },
    "params": {
        "formula": "z=(x-median(plate ctl_vector))/scale",
        "mad_to_sd": MAD_TO_SD,
        "scale_floor": f"max(1.4826*MAD, plate_scale_median*{SCALE_FLOOR_REL})",
        "mad_zero": f"raw_scale<={EPS_SCALE} → NaN（签名计算前剔除）",
        "control_type": "ctl_vector",
        "min_ctl_per_plate": MIN_CTL_PER_PLATE,
        "fallback": "0=同板 → 1=同细胞系 → 2=全局",
        "pert_type_filter": "trt_sh（精确匹配）",
        "aggregation": "instance",
        "read_chunk": READ_CHUNK,
    },
    "qc": {
        "n_trt_sh": int(len(shrna)),
        "n_ctl_vector_on_shrna_plates": int(len(ctl)),
        "n_rows_total": int(X.shape[0]),
        "n_plates": int(len(plate_stats)),
        "plates_with_lt3_ctl": int(sum(
            1 for st in plate_stats.values() if st[3] < MIN_CTL_PER_PLATE)),
        "fallback_counts": {str(k): int(v) for k, v in level_counts.items()},
        "nan_rows": int(nan_rows),
        "nan_gene_hits_total": int(nan_gene_hits.sum()),
        "nan_gene_hits_top20": {
            lm_symbols[i]: int(nan_gene_hits[i])
            for i in np.argsort(-nan_gene_hits)[:20] if nan_gene_hits[i] > 0
        },
        "nan_genes_any": int((nan_gene_hits > 0).sum()),
    },
    "elapsed_s": round(time.time() - t0, 1),
}
manifest_path = os.path.join(OUT_DIR, "manifest.json")
with open(manifest_path, "w", encoding="utf-8") as fp:
    json.dump(manifest, fp, ensure_ascii=False, indent=2)
log(f"写出 manifest；总耗时 {(time.time()-t0)/60:.1f} 分钟 → {OUT_DIR}")

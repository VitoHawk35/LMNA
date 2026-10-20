#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L8 · 重新生成与 fast_matrix.npy 列序一致的 col_sig_ids.csv（方案 A）。

背景
----
fast_matrix.npy 的列顺序 = GSE92742 Level5 GCTX 的 COL 顺序；
而 cmap_data/col_sig_ids.csv 历史上是“按 sig_id 字典序排序”的列表，
两者不一致。L5Provider / cmap 的 metadata_index 都用它建
sig_id -> 列索引 映射，因而会读到错误的签名。

本脚本只读取 GCTX 的元数据（0/META/COL/id），按该顺序导出
col_sig_ids.csv，因此不需要把 23GB 矩阵读入内存。

顺带诊断
--------
本脚本会同时核对 0/META/ROW/id 与 row_gene_ids.csv。L8 实测发现：
row_gene_ids.csv 是 gene_info 文件顺序，而 fast_matrix.npy 的行序是
GCTX ROW 顺序，两者同样错位。默认**只报告、不修改**（任务范围是列序）；
如确认要一并修复，可显式加 --fix-rows（会先备份原文件）。

用法
----
    # 1) 只检查，不写文件
    python scripts/fix_col_names.py --check

    # 2) 生成新文件到 cmap_data/col_sig_ids.fixed.csv（推荐先这样）
    python scripts/fix_col_names.py --data-dir ~/cmap/cmap_data

    # 3) 人工确认后原地替换（自动备份 col_sig_ids.csv.bak-<时间戳>）
    python scripts/fix_col_names.py --data-dir ~/cmap/cmap_data --in-place

    # 4) 可选：同时把 row_gene_ids.csv 修为 GCTX ROW 顺序（L8 额外发现）
    python scripts/fix_col_names.py --data-dir ~/cmap/cmap_data --in-place --fix-rows

    # 5) D1：数据已修复后写出完整性指纹 integrity.json（服务启动默认比对指纹）
    python scripts/fix_col_names.py --data-dir ~/cmap/cmap_data --check --write-fingerprint

依赖：h5py（服务器 cmap conda 环境已具备；LMNA 运行时不依赖本脚本）。

红线：本脚本只应在部署窗口由人执行；不要在服务运行期间反复替换数据文件。
"""
import argparse
import datetime
import os
import shutil
import sys
import tempfile

import pandas as pd

# D1：复用 backend/lincs_integrity.py 的指纹实现（两处保持一致）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
import lincs_integrity  # noqa: E402

DEFAULT_DATA_DIR = os.path.expanduser("~/cmap/cmap_data")
DEFAULT_GCTX_NAME = "GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx"
COL_HEADER = "sig_id"
ROW_HEADER = "gene_id"


def _require_h5py():
    try:
        import h5py  # noqa: F401
    except ImportError:
        sys.exit(
            "需要 h5py 才能读取 GCTX 元数据。请在服务器 cmap 环境中执行：\n"
            "  source ~/miniconda3/etc/profile.d/conda.sh && conda activate cmap"
        )
    return __import__("h5py")


def _decode(values):
    return [v.decode() if isinstance(v, bytes) else str(v) for v in values]


def read_gctx_ids(gctx_path):
    """只读 GCTX 元数据，返回 (col_ids, row_ids)。"""
    h5py = _require_h5py()
    with h5py.File(gctx_path, "r") as f:
        col_ids = _decode(f["0/META/COL/id"][:])
        row_ids = _decode(f["0/META/ROW/id"][:])
    return col_ids, row_ids


def _read_csv_ids(path, column):
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path)
    if column not in df.columns:
        raise ValueError(f"{path} 缺少列 {column!r}（实际列：{list(df.columns)}）")
    return df[column].astype(str).tolist()


def _order_report(name, current, truth):
    if not current:
        return f"  {name}: 文件不存在或为空，无法比较"
    n = min(len(current), len(truth))
    same_pos = sum(a == b for a, b in zip(current, truth))
    same_set = set(current) == set(truth)
    first = next((i for i in range(n) if current[i] != truth[i]), None)
    lines = [
        f"  {name}: {len(current)} 行，GCTX 元数据 {len(truth)} 行",
        f"    同位置一致: {same_pos}/{n}；集合相同: {same_set}",
    ]
    if len(current) != len(truth):
        lines.append(f"    [WARN] 行数不一致：文件 {len(current)} vs GCTX {len(truth)}")
    if first is not None:
        lines.append(
            f"    首个不一致位置: {first}；文件={current[first]!r}，GCTX={truth[first]!r}"
        )
    if same_pos == n and len(current) == len(truth):
        lines.append("    [OK] 顺序一致")
    else:
        lines.append("    [FAIL] 顺序不一致")
    return "\n".join(lines)


def _atomic_write_csv(ids, header, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=".l8-", suffix=".csv", dir=os.path.dirname(os.path.abspath(path))
    )
    os.close(fd)
    try:
        pd.DataFrame({header: ids}).to_csv(tmp, index=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _backup(path):
    if not os.path.exists(path):
        return None
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{path}.bak-{stamp}"
    shutil.copy2(path, backup)
    return backup


def verify_columns(gctx_path, matrix_path, col_ids, row_ids, n_samples):
    """抽样证明 fast_matrix 的列与 GCTX 行（COL 顺序）逐元素一致。"""
    import numpy as np

    h5py = _require_h5py()
    n_sigs = len(col_ids)
    n_genes = len(row_ids)
    samples = sorted({0, n_sigs // 2, n_sigs - 1})
    if n_samples and n_samples > 0:
        step = max(1, n_sigs // n_samples)
        samples = sorted(set(samples) | set(range(0, n_sigs, step)))
    samples = [i for i in samples if 0 <= i < n_sigs]

    matrix = np.memmap(matrix_path, dtype="float32", mode="r", shape=(n_genes, n_sigs))
    results = []
    with h5py.File(gctx_path, "r") as f:
        dataset = f["0/DATA/0/matrix"]
        for idx in samples:
            truth = np.asarray(dataset[idx, :], dtype=np.float32)
            got = np.asarray(matrix[:, idx], dtype=np.float32)
            max_diff = float(np.max(np.abs(got - truth)))
            results.append((idx, col_ids[idx], max_diff))
    print("  抽样列校验（fast_matrix[:, k] vs GCTX[k, :]）：")
    for idx, sid, diff in results:
        status = "[OK]" if diff < 1e-5 else "[FAIL]"
        print(f"    {status} k={idx} {sid}  max|diff|={diff:.3e}")
    return all(diff < 1e-5 for _, _, diff in results)


def main():
    parser = argparse.ArgumentParser(description="按 GCTX COL 顺序重生成 col_sig_ids.csv")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--gctx", default=None, help="GCTX 路径（默认 data-dir 下的 GSE92742 Level5）")
    parser.add_argument("--out", default=None, help="输出路径（默认 <data-dir>/col_sig_ids.fixed.csv）")
    parser.add_argument("--in-place", action="store_true", help="备份后直接替换 col_sig_ids.csv")
    parser.add_argument("--fix-rows", action="store_true",
                        help="同时把 row_gene_ids.csv 修为 GCTX ROW 顺序（L8 额外发现，默认关闭）")
    parser.add_argument("--check", action="store_true", help="只检查，不写任何文件")
    parser.add_argument("--write-fingerprint", action="store_true",
                        help="D1：花名册与 GCTX 一致后，写出 integrity.json 完整性指纹"
                             "（行/列 ID 列表 sha256、矩阵形状、3 列抽样数值哈希）；"
                             "服务启动默认（LINCS_INTEGRITY_MODE=fingerprint）比对该文件")
    parser.add_argument("--verify", type=int, default=3,
                        help="校验的抽样列数（默认 3；0 表示只校验首/中/末）")
    args = parser.parse_args()

    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    gctx_path = args.gctx or os.path.join(data_dir, DEFAULT_GCTX_NAME)
    col_path = os.path.join(data_dir, "col_sig_ids.csv")
    row_path = os.path.join(data_dir, "row_gene_ids.csv")
    matrix_path = os.path.join(data_dir, "fast_matrix.npy")
    out_path = args.out or os.path.join(data_dir, "col_sig_ids.fixed.csv")

    if not os.path.exists(gctx_path):
        sys.exit(f"GCTX 不存在: {gctx_path}")
    if not os.path.exists(matrix_path):
        sys.exit(f"fast_matrix.npy 不存在: {matrix_path}")

    print(f"[L8] data_dir = {data_dir}")
    print(f"[L8] gctx     = {gctx_path}")
    col_ids, row_ids = read_gctx_ids(gctx_path)

    if len(set(col_ids)) != len(col_ids):
        sys.exit(f"GCTX COL id 有重复：{len(col_ids)} 行，唯一 {len(set(col_ids))} 个")
    if len(set(row_ids)) != len(row_ids):
        sys.exit(f"GCTX ROW id 有重复：{len(row_ids)} 行，唯一 {len(set(row_ids))} 个")

    print("\n[L8] 顺序诊断：")
    print(_order_report("col_sig_ids.csv", _read_csv_ids(col_path, COL_HEADER), col_ids))
    row_csv = _read_csv_ids(row_path, ROW_HEADER)
    print(_order_report("row_gene_ids.csv", row_csv, row_ids))
    if row_csv and row_csv != row_ids:
        print("  [WARN] 行序也不一致：按 row_gene_ids.csv 建的行映射会取到错误基因。")
        print("    L8 按任务范围默认只报告；如需修复，加 --fix-rows（会备份原文件）。")

    ok = verify_columns(gctx_path, matrix_path, col_ids, row_ids, args.verify)
    if not ok:
        sys.exit("抽样列校验失败：fast_matrix 的列序与 GCTX COL 元数据不一致，请先查清数据来源。")

    if args.check and not args.write_fingerprint:
        print("\n[L8] --check：未写任何文件。")
        return

    if not args.check:
        if args.in_place:
            backup = _backup(col_path)
            _atomic_write_csv(col_ids, COL_HEADER, col_path)
            print(f"\n[L8] 已原地替换 {col_path}" + (f"（备份：{backup}）" if backup else ""))
        else:
            _atomic_write_csv(col_ids, COL_HEADER, out_path)
            print(f"\n[L8] 已写出 {out_path}")
            print(f"     人工确认后可执行：cp {out_path} {col_path}")

        if args.fix_rows:
            backup = _backup(row_path)
            _atomic_write_csv(row_ids, ROW_HEADER, row_path)
            print(f"[L8] 已修复行序 {row_path}" + (f"（备份：{backup}）" if backup else ""))

        print("\n[L8] 后续：删除/重建 LMNA 缓存（由人在部署窗口执行，见 deliveries/task-L8.md）")

    if args.write_fingerprint:
        # D1：指纹必须描述"正确的现状"——只有当前花名册与 GCTX 完全一致时才写，
        # 否则指纹会把错误的花名册合法化。
        current_cols = _read_csv_ids(col_path, COL_HEADER)
        current_rows = _read_csv_ids(row_path, ROW_HEADER)
        if current_cols != col_ids or current_rows != row_ids:
            sys.exit(
                "[D1] 拒绝写指纹：当前花名册与 GCTX 顺序不一致。"
                "请先执行 --in-place --fix-rows 修复，再重新生成本命令。"
            )
        fingerprint = lincs_integrity.build_fingerprint(
            matrix_path=matrix_path,
            row_csv_path=row_path,
            col_csv_path=col_path,
            row_ids=row_ids,
            col_ids=col_ids,
        )
        fp_path = lincs_integrity.write_fingerprint(
            fingerprint, os.path.join(data_dir, "integrity.json")
        )
        print(f"\n[D1] 已写出完整性指纹 {fp_path}")
        print(f"     行/列数: {fingerprint['row_count']}/{fingerprint['col_count']}，"
              f"抽样列: {[s['index'] for s in fingerprint['column_samples']]}")
        print("     服务启动默认（LINCS_INTEGRITY_MODE=fingerprint）将比对该文件。")


if __name__ == "__main__":
    main()

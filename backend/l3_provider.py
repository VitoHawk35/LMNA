#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Level 3 数据提供者（L7e 阶段 2 实施）

数据源：scripts/build_l3_derived.py 产出的派生层（默认
$CMAP_DATA_DIR/derived/l3_v1，可用 L3_DERIVED_DIR 覆盖）：

    l3_landmark.npy    (n_instances, 978) float32 robust z
                       （同板 ctl_vector median/MAD 口径，MAD=0 基因为 NaN）
    instance_meta.csv  inst_id, rna_plate, pert_id, pert_iname, cell_id,
                       pert_type, n_controls, fallback_level
    col_ids.txt        矩阵行 ID 花名册（与 npy 行一一对应）
    row_genes.csv      矩阵列花名册（entrez_id, gene_symbol，978 行）
    manifest.json      源文件/花名册 sha256、参数、QC 计数

口径要点：
- 签名侧专用：药物方法一律 NotImplementedError（药物打分走 L5，
  见 composite_provider.py）。
- pert_type == 'trt_sh' 精确匹配（禁止 startswith，防止混入
  trt_sh.cgs / trt_sh.css 共识签名）。
- 实例级聚合：每个 shRNA 孔（inst_id）是一个样本，sig_id = inst_id。
- 启动校验：花名册 sha256 与 manifest 逐一比对、形状/行数交叉核对，
  任何不一致拒绝启动（RuntimeError）。
"""

import hashlib
import json
import os
from typing import List

import numpy as np
import pandas as pd

from data_provider import IDataProvider
from config import L3_DERIVED_DIR

REQUIRED_FILES = (
    "l3_landmark.npy",
    "instance_meta.csv",
    "col_ids.txt",
    "row_genes.csv",
    "manifest.json",
)


def _sha256_lines(lines) -> str:
    """与 scripts/build_l3_derived.py 一致的花名册指纹。"""
    h = hashlib.sha256()
    for line in lines:
        h.update(str(line).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


class L3Provider(IDataProvider):
    """L3 派生层数据提供者（签名侧）。"""

    def __init__(self, root: str = None):
        self.root = root or L3_DERIVED_DIR
        if not os.path.isdir(self.root):
            raise FileNotFoundError(
                f"L3 派生层目录不存在: {self.root}。请先在服务器运行 "
                f"scripts/build_l3_derived.py（见 docs/design/L7e-spike-report.md），"
                f"或用 L3_DERIVED_DIR 指向派生层。"
            )
        missing = [
            name for name in REQUIRED_FILES
            if not os.path.exists(os.path.join(self.root, name))
        ]
        if missing:
            raise FileNotFoundError(
                f"L3 派生层 {self.root} 缺少文件: {', '.join(missing)}"
            )

        with open(os.path.join(self.root, "manifest.json"),
                  encoding="utf-8") as f:
            self.manifest = json.load(f)

        # ---- 花名册 ----
        with open(os.path.join(self.root, "col_ids.txt"),
                  encoding="utf-8") as f:
            self._col_ids = [line.strip() for line in f if line.strip()]
        row_genes = pd.read_csv(
            os.path.join(self.root, "row_genes.csv"), dtype=str)
        self._gene_symbols = row_genes["gene_symbol"].tolist()
        self._lm_entrez = row_genes["entrez_id"].tolist()

        # ---- 启动校验：行列 ID 与 manifest 逐一一致，不一致拒绝启动 ----
        expected_col_sha = self.manifest.get("matrix", {}).get("col_ids_sha256")
        actual_col_sha = _sha256_lines(self._col_ids)
        if expected_col_sha and actual_col_sha != expected_col_sha:
            raise RuntimeError(
                "L3 派生层行 ID 花名册与 manifest 不一致："
                f"col_ids.txt sha256={actual_col_sha[:12]}…，"
                f"manifest 记 {expected_col_sha[:12]}…。"
                "派生层可能被篡改或与构建清单不配套，拒绝启动。"
            )
        row_lines = [
            f"{e},{s}" for e, s in zip(self._lm_entrez, self._gene_symbols)
        ]
        expected_row_sha = self.manifest.get("matrix", {}).get("row_genes_sha256")
        actual_row_sha = _sha256_lines(row_lines)
        if expected_row_sha and actual_row_sha != expected_row_sha:
            raise RuntimeError(
                "L3 派生层列 ID（978 landmark）花名册与 manifest 不一致："
                f"row_genes.csv sha256={actual_row_sha[:12]}…，"
                f"manifest 记 {expected_row_sha[:12]}…。拒绝启动。"
            )

        # ---- 元数据 ----
        self._meta = pd.read_csv(
            os.path.join(self.root, "instance_meta.csv"),
            dtype={"inst_id": str, "rna_plate": str, "pert_id": str,
                   "pert_iname": str, "cell_id": str, "pert_type": str},
        )
        if len(self._meta) != len(self._col_ids):
            raise RuntimeError(
                f"instance_meta.csv 行数 {len(self._meta)} 与 col_ids.txt "
                f"行数 {len(self._col_ids)} 不一致，拒绝启动。"
            )
        if self._meta["inst_id"].tolist() != self._col_ids:
            raise RuntimeError(
                "instance_meta.csv 的 inst_id 顺序与 col_ids.txt 不一致，"
                "矩阵行映射不可用，拒绝启动。"
            )

        # ---- 矩阵（memmap，行=实例） ----
        shape = self.manifest.get("matrix", {}).get("shape")
        self._matrix = np.load(
            os.path.join(self.root, "l3_landmark.npy"), mmap_mode="r")
        if self._matrix.ndim != 2 or \
                self._matrix.shape != (len(self._col_ids), len(self._gene_symbols)):
            raise RuntimeError(
                f"l3_landmark.npy 形状 {tuple(self._matrix.shape)} 与花名册 "
                f"({len(self._col_ids)}, {len(self._gene_symbols)}) 不一致，拒绝启动。"
            )
        if shape and list(self._matrix.shape) != list(shape):
            raise RuntimeError(
                f"l3_landmark.npy 形状 {tuple(self._matrix.shape)} 与 manifest "
                f"{shape} 不一致，拒绝启动。"
            )

        self._row_of_inst = {inst: i for i, inst in enumerate(self._col_ids)}

        # trt_sh 精确匹配（禁止 startswith）；sig_id = inst_id（实例级）
        self._shrna_df = self._meta[
            self._meta["pert_type"] == "trt_sh"
        ].copy()
        self._shrna_df["sig_id"] = self._shrna_df["inst_id"]

        print(
            f"[L3Provider] 派生层 {self.root}：{len(self._col_ids)} 实例 × "
            f"{len(self._gene_symbols)} landmark，"
            f"trt_sh {len(self._shrna_df)}，构建 "
            f"{self.manifest.get('created_at', '?')}"
        )

    # ------------------------------------------------------------------
    # IDataProvider 接口实现（签名侧）
    # ------------------------------------------------------------------

    def get_shrna_samples(self, gene_name: str) -> pd.DataFrame:
        gene_upper = gene_name.strip().upper()
        return self._shrna_df[
            self._shrna_df["pert_iname"].str.upper() == gene_upper
        ].copy()

    def get_all_shrna_samples(self) -> pd.DataFrame:
        return self._shrna_df.copy()

    def get_expression_matrix(self, sig_ids: List[str]) -> np.ndarray:
        """按 inst_id 取行，返回 (978, n) float32（landmark 行序）。"""
        rows = []
        for sid in sig_ids:
            idx = self._row_of_inst.get(sid)
            if idx is None:
                raise KeyError(f"L3 派生层不存在实例: {sid}")
            rows.append(idx)
        if not rows:
            return np.empty((len(self._gene_symbols), 0), dtype=np.float32)
        # 行=实例存储：取行后转置为 (978, n)
        return np.asarray(self._matrix[rows, :], dtype=np.float32).T

    def get_gene_symbols(self) -> List[str]:
        return list(self._gene_symbols)

    def get_lm_gene_indices(self) -> np.ndarray:
        # 派生层只有 978 个 landmark 列，索引即 0..977
        return np.arange(len(self._gene_symbols), dtype=np.int32)

    def get_vehicle_samples_for_plate(self, plate_id: str) -> List[str]:
        """同板 ctl_vector（shRNA 实验的"vehicle"=空载体，见设计文档 §2.2）。"""
        df = self._meta[
            (self._meta["rna_plate"] == plate_id) &
            (self._meta["pert_type"] == "ctl_vector")
        ]
        return df["inst_id"].tolist()

    def list_available_genes(self) -> List[str]:
        genes = (
            self._shrna_df["pert_iname"].dropna().astype(str)
            .str.upper().unique().tolist()
        )
        return sorted(genes)

    # ------------------------------------------------------------------
    # 药物侧：L3 不提供（药物打分走 L5，见 CompositeProvider）
    # ------------------------------------------------------------------

    def get_drug_samples(self) -> pd.DataFrame:
        raise NotImplementedError(
            "L3 仅用于签名侧；药物样本请用 L5（CompositeProvider 已自动组合）"
        )

    def get_drug_expression_matrix(self, sig_ids: List[str]) -> np.ndarray:
        raise NotImplementedError(
            "L3 仅用于签名侧；药物矩阵请用 L5（CompositeProvider 已自动组合）"
        )

    def get_drug_name_map(self) -> pd.Series:
        raise NotImplementedError(
            "L3 仅用于签名侧；药物名映射请用 L5（CompositeProvider 已自动组合）"
        )

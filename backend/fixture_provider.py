#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
夹具数据提供者

读取 LMNA_FIXTURE_DIR 下的 4 个夹具文件，提供与 L5Provider 相同的数据接口，
使测试不需要 64GB 原始数据即可运行。

夹具文件：
    lmna_fixture.npz      gene_symbols(978), sh_matrix(978 x n_sh), cp_matrix(978 x n_cp)
    lmna_fixture_sh.tsv   sig_id, pert_id, pert_iname, cell_id, pert_type（shRNA 样本）
    lmna_fixture_cp.tsv   同列（药物级中位数签名）
    lmna_fixture_meta.json 每个靶点的已知抑制剂名单
"""

import json
import os
from typing import List

import numpy as np
import pandas as pd

from data_provider import IDataProvider

_FIXTURE_FILES = (
    "lmna_fixture.npz",
    "lmna_fixture_sh.tsv",
    "lmna_fixture_cp.tsv",
    "lmna_fixture_meta.json",
)


class FixtureProvider(IDataProvider):
    """从本地小夹具读取数据的数据提供者。"""

    def __init__(self, fixture_dir: str = None):
        fixture_dir = fixture_dir or os.getenv("LMNA_FIXTURE_DIR")
        if not fixture_dir:
            raise FileNotFoundError(
                "未设置 LMNA_FIXTURE_DIR，无法使用 FixtureProvider"
            )
        if not os.path.isdir(fixture_dir):
            raise FileNotFoundError(f"夹具目录不存在: {fixture_dir}")

        missing = [
            name for name in _FIXTURE_FILES
            if not os.path.exists(os.path.join(fixture_dir, name))
        ]
        if missing:
            raise FileNotFoundError(
                f"夹具目录 {fixture_dir} 缺少文件: {', '.join(missing)}"
            )

        self.fixture_dir = fixture_dir

        npz_path = os.path.join(fixture_dir, "lmna_fixture.npz")
        with np.load(npz_path, allow_pickle=False) as data:
            self._gene_symbols = [str(s) for s in data["gene_symbols"].tolist()]
            self._sh_matrix = np.asarray(data["sh_matrix"], dtype=np.float32)
            self._cp_matrix = np.asarray(data["cp_matrix"], dtype=np.float32)

        self._sh_df = self._read_meta_tsv("lmna_fixture_sh.tsv")
        self._cp_df = self._read_meta_tsv("lmna_fixture_cp.tsv")

        if self._sh_matrix.shape[1] != len(self._sh_df):
            raise ValueError(
                "lmna_fixture_sh.tsv 行数与 sh_matrix 列数不一致: "
                f"{len(self._sh_df)} vs {self._sh_matrix.shape[1]}"
            )
        if self._cp_matrix.shape[1] != len(self._cp_df):
            raise ValueError(
                "lmna_fixture_cp.tsv 行数与 cp_matrix 列数不一致: "
                f"{len(self._cp_df)} vs {self._cp_matrix.shape[1]}"
            )
        if self._sh_matrix.shape[0] != len(self._gene_symbols):
            raise ValueError(
                "gene_symbols 长度与矩阵行数不一致: "
                f"{len(self._gene_symbols)} vs {self._sh_matrix.shape[0]}"
            )

        self._sh_sig_to_idx = {
            sid: i for i, sid in enumerate(self._sh_df["sig_id"].tolist())
        }
        self._cp_sig_to_idx = {
            sid: i for i, sid in enumerate(self._cp_df["sig_id"].tolist())
        }

        meta_path = os.path.join(fixture_dir, "lmna_fixture_meta.json")
        with open(meta_path, "r", encoding="utf-8") as f:
            self.meta = json.load(f)

    def _read_meta_tsv(self, filename: str) -> pd.DataFrame:
        df = pd.read_csv(
            os.path.join(self.fixture_dir, filename),
            sep="\t",
            dtype=str,
            keep_default_na=False,
        )
        required = {"sig_id", "pert_id", "pert_iname", "cell_id", "pert_type"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"{filename} 缺少列: {sorted(missing)}")
        return df

    # ------------------------------------------------------------------
    # IDataProvider 接口实现
    # ------------------------------------------------------------------

    def get_shrna_samples(self, gene_name: str) -> pd.DataFrame:
        gene_upper = gene_name.strip().upper()
        mask = self._sh_df["pert_iname"].str.upper() == gene_upper
        return self._sh_df[mask].copy()

    def get_all_shrna_samples(self) -> pd.DataFrame:
        return self._sh_df.copy()

    def get_expression_matrix(self, sig_ids: List[str]) -> np.ndarray:
        """在 shRNA 和化合物两张表中按 sig_id 查找列。"""
        columns = []
        for sid in sig_ids:
            if sid in self._sh_sig_to_idx:
                columns.append(self._sh_matrix[:, self._sh_sig_to_idx[sid]])
            elif sid in self._cp_sig_to_idx:
                columns.append(self._cp_matrix[:, self._cp_sig_to_idx[sid]])
            else:
                raise KeyError(f"夹具中不存在 sig_id: {sid}")
        if not columns:
            return np.empty((len(self._gene_symbols), 0), dtype=np.float32)
        return np.stack(columns, axis=1).astype(np.float32, copy=False)

    def get_gene_symbols(self) -> List[str]:
        return list(self._gene_symbols)

    def get_drug_samples(self) -> pd.DataFrame:
        return self._cp_df.copy()

    def get_drug_expression_matrix(self, sig_ids: List[str]) -> np.ndarray:
        columns = []
        for sid in sig_ids:
            if sid not in self._cp_sig_to_idx:
                raise KeyError(f"夹具中不存在化合物 sig_id: {sid}")
            columns.append(self._cp_matrix[:, self._cp_sig_to_idx[sid]])
        if not columns:
            return np.empty((len(self._gene_symbols), 0), dtype=np.float32)
        return np.stack(columns, axis=1).astype(np.float32, copy=False)

    def get_lm_gene_indices(self) -> np.ndarray:
        # 夹具矩阵本身已经是 978 个 landmark 基因，索引即 0..977
        return np.arange(len(self._gene_symbols), dtype=np.int32)

    def get_vehicle_samples_for_plate(self, plate_id: str) -> List[str]:
        raise NotImplementedError("夹具不包含板级 vehicle 对照信息")

    def list_available_genes(self) -> List[str]:
        genes = (
            self._sh_df["pert_iname"]
            .dropna()
            .astype(str)
            .str.upper()
            .unique()
            .tolist()
        )
        return sorted(genes)

    def get_drug_name_map(self) -> pd.Series:
        return pd.Series(
            self._cp_df["pert_iname"].values,
            index=self._cp_df["sig_id"].values,
            dtype=object,
        )

    # ------------------------------------------------------------------
    # 夹具附加信息
    # ------------------------------------------------------------------

    def get_target_inhibitors(self) -> dict:
        """返回 {靶点: [已知抑制剂]}（来自 lmna_fixture_meta.json）。"""
        targets = self.meta.get("targets", {})
        return {
            gene: list(info.get("inhibitors", []))
            for gene, info in targets.items()
        }

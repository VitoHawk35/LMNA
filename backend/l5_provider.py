#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Level 5 数据提供者实现
基于现有 fast_matrix.npy（memmap 格式）和元数据文件
"""

import os
import numpy as np
import pandas as pd
from typing import List

from data_provider import IDataProvider
from config import (
    MATRIX_PATH, COL_NAMES_PATH, ROW_NAMES_PATH,
    SIG_INFO_PATH, GENE_INFO_PATH,
    N_GENES, N_SIGS
)


class L5Provider(IDataProvider):
    """
    L5 数据提供者
    直接使用现有的聚合后签名级 z-score 数据
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True

        # 1. 加载 memmap 矩阵
        if not os.path.exists(MATRIX_PATH):
            raise FileNotFoundError(f"矩阵文件不存在: {MATRIX_PATH}")
        self._matrix = np.memmap(
            MATRIX_PATH,
            dtype='float32',
            mode='r',
            shape=(N_GENES, N_SIGS)
        )

        # 2. 加载列名（sig_id 顺序）
        self._col_names = pd.read_csv(COL_NAMES_PATH)['sig_id'].tolist()
        self._sig_id_to_idx = {sid: i for i, sid in enumerate(self._col_names)}

        # 3. 加载基因信息，找出 landmark 基因
        self._gene_info = pd.read_csv(GENE_INFO_PATH, sep='\t')
        self._row_gene_ids = pd.read_csv(ROW_NAMES_PATH)['gene_id'].tolist()

        # 建立 gene_id -> 行索引 映射
        self._gene_id_to_row = {gid: i for i, gid in enumerate(self._row_gene_ids)}

        # 找出 landmark 基因在矩阵中的行索引
        lm_genes = self._gene_info[self._gene_info['pr_is_lm'] == 1]
        self._lm_gene_ids = lm_genes['pr_gene_id'].tolist()
        self._lm_gene_symbols = [
            self._gene_info[self._gene_info['pr_gene_id'] == gid]['pr_gene_symbol'].values[0]
            for gid in self._lm_gene_ids
        ]

        # landmark 基因在完整 12328 矩阵中的行索引
        self._lm_indices = np.array(
            [self._gene_id_to_row[gid] for gid in self._lm_gene_ids],
            dtype=np.int32
        )

        # 4. 加载签名信息
        self._sig_info = pd.read_csv(
            SIG_INFO_PATH, sep='\t',
            dtype={
                'sig_id': str, 'pert_id': str, 'pert_iname': str,
                'pert_type': str, 'cell_id': str, 'distil_id': str
            },
            low_memory=False
        )

        # 5. 缓存常用查询
        # 只保留真正的 shRNA 敲低实例，排除 trt_sh.cgs 共识签名等派生类型
        self._shrna_df = self._sig_info[
            self._sig_info['pert_type'] == 'trt_sh'
        ].copy()

        self._drug_df = self._sig_info[
            self._sig_info['pert_type'] == 'trt_cp'
        ].copy()

        # 药物名映射
        self._drug_name_map = pd.Series(
            self._drug_df['pert_iname'].values,
            index=self._drug_df['sig_id'].values
        )

    # ------------------------------------------------------------------
    # IDataProvider 接口实现
    # ------------------------------------------------------------------

    def get_shrna_samples(self, gene_name: str) -> pd.DataFrame:
        gene_upper = gene_name.strip().upper()
        df = self._shrna_df[
            self._shrna_df['pert_iname'].str.upper() == gene_upper
        ].copy()
        return df

    def get_all_shrna_samples(self) -> pd.DataFrame:
        return self._shrna_df.copy()

    def get_expression_matrix(self, sig_ids: List[str], chunk_size: int = 5000) -> np.ndarray:
        """
        分块提取表达矩阵，避免一次性读取大量列导致内存和 I/O 瓶颈。
        """
        indices = [self._sig_id_to_idx[sid] for sid in sig_ids]
        n = len(indices)
        result = np.empty((len(self._lm_gene_symbols), n), dtype=np.float32)

        for start in range(0, n, chunk_size):
            end = min(start + chunk_size, n)
            idx_chunk = indices[start:end]
            # memmap 视图 + copy，只取 landmark 行
            full_cols = self._matrix[:, idx_chunk]
            result[:, start:end] = full_cols[self._lm_indices, :]

        return result

    def get_gene_symbols(self) -> List[str]:
        return self._lm_gene_symbols.copy()

    def get_drug_samples(self) -> pd.DataFrame:
        return self._drug_df.copy()

    def get_drug_expression_matrix(self, sig_ids: List[str]) -> np.ndarray:
        return self.get_expression_matrix(sig_ids)

    def get_lm_gene_indices(self) -> np.ndarray:
        return self._lm_indices.copy()

    def get_vehicle_samples_for_plate(self, plate_id: str) -> List[str]:
        raise NotImplementedError(
            "L5 数据不包含原始板级 vehicle 对照信息，"
            "请使用 L3Provider 或直接用 L5 z-score"
        )

    def list_available_genes(self) -> List[str]:
        genes = self._shrna_df['pert_iname'].dropna().str.upper().unique().tolist()
        return sorted(genes)

    def get_drug_name_map(self) -> pd.Series:
        return self._drug_name_map.copy()

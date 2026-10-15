#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Level 3 数据提供者（预留实现）
后续接入服务器上的 Level 3 原始数据时使用
"""

import numpy as np
import pandas as pd
from typing import List

from data_provider import IDataProvider


class L3Provider(IDataProvider):
    """
    L3 数据提供者
    基于 Level 3 归一化表达值，按 384 孔板分组，
    相对同板 vehicle 对照重算 robust z-score
    """

    def __init__(self):
        raise NotImplementedError(
            "L3Provider 尚未实现。请先配置 Level 3 数据路径，"
            "然后实现以下功能：\n"
            "1. 读取 Level 3 表达矩阵\n"
            "2. 解析 distil_id 提取板号\n"
            "3. 按板分组，提取 vehicle 对照\n"
            "4. 计算 robust z-score: (x - median) / (MAD * 1.482)\n"
        )

    def get_shrna_samples(self, gene_name: str) -> pd.DataFrame:
        raise NotImplementedError

    def get_expression_matrix(self, sig_ids: List[str]) -> np.ndarray:
        raise NotImplementedError

    def get_gene_symbols(self) -> List[str]:
        raise NotImplementedError

    def get_drug_samples(self) -> pd.DataFrame:
        raise NotImplementedError

    def get_drug_expression_matrix(self, sig_ids: List[str]) -> np.ndarray:
        raise NotImplementedError

    def get_lm_gene_indices(self) -> np.ndarray:
        raise NotImplementedError

    def get_vehicle_samples_for_plate(self, plate_id: str) -> List[str]:
        raise NotImplementedError

    def list_available_genes(self) -> List[str]:
        raise NotImplementedError

    def get_drug_name_map(self) -> pd.Series:
        raise NotImplementedError

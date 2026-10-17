#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据提供者抽象基类
"""

from abc import ABC, abstractmethod
from typing import List, Tuple
import numpy as np
import pandas as pd


class IDataProvider(ABC):
    """CMAP 数据访问抽象接口"""

    @abstractmethod
    def get_shrna_samples(self, gene_name: str) -> pd.DataFrame:
        """
        获取某基因的所有 shRNA 敲低样本信息

        Returns:
            DataFrame，至少包含 sig_id 列
        """
        pass

    @abstractmethod
    def get_expression_matrix(self, sig_ids: List[str]) -> np.ndarray:
        """
        获取指定签名在 978 landmark 基因上的表达矩阵

        Args:
            sig_ids: 签名 ID 列表

        Returns:
            np.ndarray, shape=(978, len(sig_ids)), dtype=float32
        """
        pass

    @abstractmethod
    def get_all_shrna_samples(self) -> pd.DataFrame:
        """
        获取所有 shRNA 敲低样本信息（不是某个基因的子集）

        供 SignatureEngine 构建全局 shRNA null 池使用，替代对 provider
        私有属性（如 _shrna_df）的访问。

        Returns:
            DataFrame，至少包含 sig_id 列；调用方不应修改返回对象
        """
        pass

    @abstractmethod
    def get_gene_symbols(self) -> List[str]:
        """
        获取 978 个 landmark gene symbol 列表（按矩阵行顺序）

        Returns:
            长度为 978 的字符串列表
        """
        pass

    @abstractmethod
    def get_drug_samples(self) -> pd.DataFrame:
        """
        获取所有化合物处理样本信息

        Returns:
            DataFrame，至少包含 sig_id 列
        """
        pass

    @abstractmethod
    def get_drug_expression_matrix(self, sig_ids: List[str]) -> np.ndarray:
        """
        获取指定药物签名在 978 landmark 基因上的表达矩阵

        Args:
            sig_ids: 签名 ID 列表

        Returns:
            np.ndarray, shape=(978, len(sig_ids))
        """
        pass

    @abstractmethod
    def get_lm_gene_indices(self) -> np.ndarray:
        """
        获取 landmark 基因在完整 12328 维向量中的索引

        Returns:
            np.ndarray, shape=(978,)，dtype=int
        """
        pass

    @abstractmethod
    def get_vehicle_samples_for_plate(self, plate_id: str) -> List[str]:
        """
        获取某块 384 孔板上的所有 vehicle 对照样本 sig_id
        L5 实现可抛出 NotImplementedError
        """
        pass

    @abstractmethod
    def list_available_genes(self) -> List[str]:
        """
        列出所有有 shRNA 数据的基因名（大写唯一）

        Returns:
            基因名字符串列表
        """
        pass

    @abstractmethod
    def get_drug_name_map(self) -> pd.Series:
        """
        返回 sig_id -> pert_iname 的映射（仅化合物）

        Returns:
            pd.Series，index=sig_id, values=pert_iname
        """
        pass

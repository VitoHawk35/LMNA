#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
组合数据提供者（L7e 阶段 2）

签名侧 → L3Provider（Level 3 + 同板 ctl_vector robust z，实例级）
药物侧 → L5Provider（MODZ 药物中位数矩阵）

为什么必须组合而不是单 L3Provider：
- L3 派生层只覆盖 shRNA/ctl_vector 实例的 landmark robust z，不含化合物
  签名；药物打分仍用 L5 的 MODZ 口径（两套 z-score 不混用，见
  docs/design/L7e-l3-provider.md §1 推荐 3 / spike 报告 §7-4）。
- IDataProvider 的签名方法与药物方法在此分别路由，XSum 打分用的
  978 landmark 基因顺序在启动时校验两侧一致，不一致拒绝启动。
"""

from typing import List

import numpy as np
import pandas as pd

from data_provider import IDataProvider
from l3_provider import L3Provider
from l5_provider import L5Provider


class CompositeProvider(IDataProvider):
    """L3 签名 + L5 药物的组合提供者。"""

    def __init__(self, signature_provider: IDataProvider = None,
                 drug_provider: IDataProvider = None):
        self._sig = signature_provider or L3Provider()
        self._drug = drug_provider or L5Provider()

        sig_symbols = self._sig.get_gene_symbols()
        drug_symbols = self._drug.get_gene_symbols()
        if list(sig_symbols) != list(drug_symbols):
            raise RuntimeError(
                "签名侧与药物侧的 978 landmark 基因顺序不一致：XSum 打分按"
                "基因下标对齐两套矩阵，顺序不同会把分数打到错误的基因上，"
                "拒绝启动。"
                f"（签名侧前 5: {list(sig_symbols)[:5]}，"
                f"药物侧前 5: {list(drug_symbols)[:5]}）"
            )

        sig_desc = getattr(self._sig, "root", type(self._sig).__name__)
        drug_desc = type(self._drug).__name__
        print(
            f"[CompositeProvider] 签名数据源 = {type(self._sig).__name__}"
            f"（{sig_desc}），药物数据源 = {drug_desc}"
        )

    # 便于诊断/日志
    @property
    def signature_provider(self) -> IDataProvider:
        return self._sig

    @property
    def drug_provider(self) -> IDataProvider:
        return self._drug

    # ------------------------------------------------------------------
    # 签名侧 → L3
    # ------------------------------------------------------------------

    def get_shrna_samples(self, gene_name: str) -> pd.DataFrame:
        return self._sig.get_shrna_samples(gene_name)

    def get_all_shrna_samples(self) -> pd.DataFrame:
        return self._sig.get_all_shrna_samples()

    def get_expression_matrix(self, sig_ids: List[str]) -> np.ndarray:
        return self._sig.get_expression_matrix(sig_ids)

    def get_gene_symbols(self) -> List[str]:
        return self._sig.get_gene_symbols()

    def get_lm_gene_indices(self) -> np.ndarray:
        return self._sig.get_lm_gene_indices()

    def get_vehicle_samples_for_plate(self, plate_id: str) -> List[str]:
        return self._sig.get_vehicle_samples_for_plate(plate_id)

    def list_available_genes(self) -> List[str]:
        return self._sig.list_available_genes()

    # ------------------------------------------------------------------
    # 药物侧 → L5
    # ------------------------------------------------------------------

    def get_drug_samples(self) -> pd.DataFrame:
        return self._drug.get_drug_samples()

    def get_drug_expression_matrix(self, sig_ids: List[str]) -> np.ndarray:
        return self._drug.get_drug_expression_matrix(sig_ids)

    def get_drug_name_map(self) -> pd.Series:
        return self._drug.get_drug_name_map()

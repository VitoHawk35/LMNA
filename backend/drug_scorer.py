#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
药物打分器
支持 XSUM 和 WTCS 两种算法
使用药物中位数矩阵缓存加速。
"""

import numpy as np
import pandas as pd
from typing import Dict

from data_provider import IDataProvider
from config import DEFAULT_TOP_K, DEFAULT_BOTTOM_K
from drug_median_cache import get_drug_median_matrix


class DrugScorer:
    """
    基于基因签名对化合物进行反转打分。
    """

    def __init__(self, provider: IDataProvider):
        self.provider = provider
        self._drug_matrix, self._drug_names = get_drug_median_matrix(provider)

    def score_drugs(
        self,
        signature: Dict,
        method: str = "xsum",
        top_k: int = DEFAULT_TOP_K,
        bottom_k: int = DEFAULT_BOTTOM_K
    ) -> Dict:
        """
        用指定方法对药物进行打分。
        """
        method = method.lower()
        if method == "xsum":
            return self._xsum_score(signature, top_k, bottom_k)
        elif method == "wtcs":
            return self._wtcs_score(signature, top_k, bottom_k)
        else:
            raise ValueError(f"不支持的打分方法: {method}")

    def _xsum_score(self, signature: Dict, top_k: int, bottom_k: int) -> Dict:
        """XSUM 算法。"""
        up_genes = signature["up_genes"]
        down_genes = signature["down_genes"]
        gene_symbols = self.provider.get_gene_symbols()
        symbol_to_idx = {s: i for i, s in enumerate(gene_symbols)}

        up_indices = [symbol_to_idx[g] for g in up_genes if g in symbol_to_idx]
        down_indices = [symbol_to_idx[g] for g in down_genes if g in symbol_to_idx]

        # 统一符号约定：mimic = Σz(up) − Σz(down)，score = −mimic
        # 即 score = −Σz_up + Σz_down，高分 = 逆转
        score_vec = np.zeros(self._drug_matrix.shape[1])
        if up_indices:
            score_vec -= np.sum(self._drug_matrix[up_indices, :], axis=0)
        if down_indices:
            score_vec += np.sum(self._drug_matrix[down_indices, :], axis=0)

        df = pd.DataFrame({
            "drug_name": self._drug_names,
            "score": score_vec
        })
        df = df.sort_values("score", ascending=False).reset_index(drop=True)

        top = df.head(top_k)
        bottom = df.tail(bottom_k).iloc[::-1]

        return {
            "method": "xsum",
            "gene_name": signature["gene_name"],
            "n_up_genes": len(up_genes),
            "n_down_genes": len(down_genes),
            "top_drugs": [
                {"drug_name": row["drug_name"], "score": round(row["score"], 4)}
                for _, row in top.iterrows()
            ],
            "bottom_drugs": [
                {"drug_name": row["drug_name"], "score": round(row["score"], 4)}
                for _, row in bottom.iterrows()
            ],
            "all_scores": df.to_dict("records"),
        }

    def _wtcs_score(self, signature: Dict, top_k: int, bottom_k: int) -> Dict:
        """WTCS 算法。"""
        up_genes = signature["up_genes"]
        down_genes = signature["down_genes"]
        gene_symbols = self.provider.get_gene_symbols()
        symbol_to_idx = {s: i for i, s in enumerate(gene_symbols)}

        up_indices = [symbol_to_idx[g] for g in up_genes if g in symbol_to_idx]
        down_indices = [symbol_to_idx[g] for g in down_genes if g in symbol_to_idx]

        G = self._drug_matrix.shape[0]
        # 对中位数矩阵每列计算排名
        ranks = np.argsort(np.argsort(-self._drug_matrix, axis=0), axis=0) + 1
        weights = (G + 1) - 2 * ranks

        score_vec = np.zeros(self._drug_matrix.shape[1])
        if up_indices:
            score_vec -= np.sum(weights[up_indices, :], axis=0)
        if down_indices:
            score_vec += np.sum(weights[down_indices, :], axis=0)

        df = pd.DataFrame({
            "drug_name": self._drug_names,
            "score": score_vec
        })
        df = df.sort_values("score", ascending=False).reset_index(drop=True)

        max_abs = df["score"].abs().max()
        if max_abs > 0:
            df["score"] = df["score"] / max_abs

        top = df.head(top_k)
        bottom = df.tail(bottom_k).iloc[::-1]

        return {
            "method": "wtcs",
            "gene_name": signature["gene_name"],
            "n_up_genes": len(up_genes),
            "n_down_genes": len(down_genes),
            "top_drugs": [
                {"drug_name": row["drug_name"], "score": round(row["score"], 4)}
                for _, row in top.iterrows()
            ],
            "bottom_drugs": [
                {"drug_name": row["drug_name"], "score": round(row["score"], 4)}
                for _, row in bottom.iterrows()
            ],
            "all_scores": df.to_dict("records"),
        }

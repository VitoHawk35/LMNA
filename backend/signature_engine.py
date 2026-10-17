#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
签名计算引擎
Rank of Ranks + Kolmogorov-Smirnov + Bootstrap + BH 校正

优化策略：
- 使用分块读取构建全局 shRNA 排名缓存
- 排名缓存为 int16 memmap，大小约 424MB (216081*978*2)
- 后续启动直接读取缓存，秒开
"""

import os
import numpy as np
from typing import Dict, List

from data_provider import IDataProvider
from config import (
    KS_THRESHOLD, FDR_THRESHOLD, BOOTSTRAP_N, RANDOM_SEED,
    CACHE_DIR, FAST_MODE_TOP_N, MAX_GENES_PER_DIRECTION,
    signature_params
)


# 全局排名缓存文件
_SHRNA_RANK_CACHE = os.path.join(CACHE_DIR, "_shrna_rank_matrix.dat")
_SHRNA_RANK_SHAPE = os.path.join(CACHE_DIR, "_shrna_rank_shape.txt")


def _ensure_shrna_rank_cache(provider: IDataProvider) -> np.ndarray:
    """
    懒加载并缓存所有 shRNA 样本的列内排名矩阵。
    缓存为 numpy memmap 文件。
    """
    shrna_df = provider.get_all_shrna_samples()
    n_shrna = len(shrna_df)
    n_genes = len(provider.get_gene_symbols())

    if os.path.exists(_SHRNA_RANK_SHAPE):
        with open(_SHRNA_RANK_SHAPE, 'r', encoding='utf-8') as f:
            cached_shape = tuple(map(int, f.read().strip().split(',')))
        if cached_shape == (n_genes, n_shrna):
            print(f"[SignatureEngine] 从缓存加载 shRNA 排名矩阵: {cached_shape}")
            return np.memmap(
                _SHRNA_RANK_CACHE,
                dtype='int16',
                mode='r',
                shape=cached_shape
            )

    print(f"[SignatureEngine] 首次构建 shRNA 排名矩阵 ({n_shrna} 样本)...")
    sig_ids = shrna_df['sig_id'].tolist()

    # 分块读取并计算排名，避免一次性加载大矩阵
    CHUNK = 5000
    rank_chunks = []
    for start in range(0, n_shrna, CHUNK):
        end = min(start + CHUNK, n_shrna)
        chunk_sigs = sig_ids[start:end]
        expr_chunk = provider.get_expression_matrix(chunk_sigs)
        # 列内降序排名：1=最高，978=最低
        ranks = np.argsort(np.argsort(-expr_chunk, axis=0), axis=0).astype(np.int16) + 1
        rank_chunks.append(ranks)
        print(f"[SignatureEngine] 排名计算进度: {end}/{n_shrna}")

    rank_matrix = np.hstack(rank_chunks)

    # 写入 memmap 缓存
    fp = np.memmap(_SHRNA_RANK_CACHE, dtype='int16', mode='w+', shape=rank_matrix.shape)
    fp[:] = rank_matrix[:]
    fp.flush()
    del fp

    with open(_SHRNA_RANK_SHAPE, 'w', encoding='utf-8') as f:
        f.write(f"{rank_matrix.shape[0]},{rank_matrix.shape[1]}")

    return np.memmap(
        _SHRNA_RANK_CACHE,
        dtype='int16',
        mode='r',
        shape=rank_matrix.shape
    )


def ks_uniform_batch(ranks_matrix: np.ndarray, G: int) -> np.ndarray:
    """
    向量化计算多个基因的带符号 KS 统计量。

    统一符号约定：KS > 0 = 敲低后该基因上调（进 up_genes）；KS < 0 = 下调。
    样本内秩 1 = 表达最高，G = 最低。
    """
    N = ranks_matrix.shape[1]
    ranks_sorted = np.sort(ranks_matrix, axis=1)
    i = np.arange(1, N + 1)
    D_plus = np.max(i / N - ranks_sorted / G, axis=1)
    D_minus = np.max(ranks_sorted / G - (i - 1) / N, axis=1)
    scores = np.where(D_plus >= D_minus, D_plus, -D_minus)
    return scores


class SignatureEngine:
    """
    基因敲低签名计算引擎
    """

    def __init__(self, provider: IDataProvider):
        self.provider = provider
        self._rng = np.random.default_rng(RANDOM_SEED)
        self._shrna_rank_matrix = _ensure_shrna_rank_cache(provider)
        # 列顺序与 _shrna_rank_matrix 一致：用于剔除目标基因自身样本
        self._shrna_samples = provider.get_all_shrna_samples()
        self._shrna_gene_symbols = self.provider.get_gene_symbols()
        self._n_genes = len(self._shrna_gene_symbols)
        print(f"[SignatureEngine] 准备就绪，shRNA 池大小={self._shrna_rank_matrix.shape[1]}")

    def compute_signature(self, gene_name: str) -> Dict:
        """
        计算某基因的敲低签名。
        """
        # 1. 获取目标基因的 shRNA 样本
        target_df = self.provider.get_shrna_samples(gene_name)
        n_samples = len(target_df)
        if n_samples == 0:
            raise ValueError(f"基因 {gene_name} 没有 shRNA 敲低数据")

        target_sig_ids = target_df['sig_id'].tolist()
        target_expr = self.provider.get_expression_matrix(target_sig_ids)

        # 2. 样本内排名
        target_ranks = np.argsort(np.argsort(-target_expr, axis=0), axis=0).astype(np.int16) + 1

        # 3. 计算观测 KS 分数（G 由数据推导）
        G = self._n_genes
        observed_ks = ks_uniform_batch(target_ranks, G)

        # 4. Bootstrap null distribution（剔除目标基因自身的样本列）
        target_mask = (
            self._shrna_samples['pert_iname']
            .fillna('')
            .astype(str)
            .str.upper()
            .to_numpy() == gene_name.strip().upper()
        )
        exclude_cols = np.flatnonzero(target_mask)
        print(f"[SignatureEngine] 开始 Bootstrap ({BOOTSTRAP_N} 次)...")
        n_pool = self._shrna_rank_matrix.shape[1]
        null_ks_matrix = self._bootstrap_null_ks(
            n_pool, n_samples, BOOTSTRAP_N, exclude_cols
        )

        # 5. P value：+1 平滑，避免 p=0，最小 p = 1/(B+1)
        observed_ks_abs = np.abs(observed_ks)
        null_ks_abs = np.abs(null_ks_matrix)
        B = null_ks_abs.shape[0]
        p_values = (
            np.sum(null_ks_abs >= observed_ks_abs, axis=0) + 1
        ) / (B + 1)

        # 6. BH 校正
        fdr_values = self._benjamini_hochberg(p_values)

        # 7. 筛选签名基因
        symbols = self._shrna_gene_symbols
        up_sig = []    # (symbol, ks)，ks > 0
        down_sig = []  # (symbol, ks)，ks < 0
        ks_dict = {}
        p_dict = {}
        fdr_dict = {}

        for i, sym in enumerate(symbols):
            ks = observed_ks[i]
            p = p_values[i]
            fdr = fdr_values[i]
            ks_dict[sym] = float(ks)
            p_dict[sym] = float(p)
            fdr_dict[sym] = float(fdr)

            if fdr < FDR_THRESHOLD and abs(ks) > KS_THRESHOLD:
                if ks > 0:
                    up_sig.append((sym, float(ks)))
                else:
                    down_sig.append((sym, float(ks)))

        # n_sig = 封顶之前通过 FDR + KS 的基因数（L3 判档要用）
        n_sig = len(up_sig) + len(down_sig)

        fast_mode_used = False
        # 快速模式：如果统计筛选未得到基因，直接取 |KS| 最大的 N 个
        if FAST_MODE_TOP_N > 0 and n_sig == 0:
            fast_mode_used = True
            print(f"[SignatureEngine] 快速模式：取 |KS| 最大的 {FAST_MODE_TOP_N} 个基因")
            abs_ks = np.abs(observed_ks)
            top_indices = np.argsort(-abs_ks)[:FAST_MODE_TOP_N]
            for i in top_indices:
                sym = symbols[i]
                ks = float(observed_ks[i])
                if ks > 0:
                    up_sig.append((sym, ks))
                else:
                    down_sig.append((sym, ks))

        # 每方向按 KS 强度排序后封顶（0 = 不封顶）
        up_sig.sort(key=lambda item: item[1], reverse=True)
        down_sig.sort(key=lambda item: item[1])
        if MAX_GENES_PER_DIRECTION > 0:
            up_sig = up_sig[:MAX_GENES_PER_DIRECTION]
            down_sig = down_sig[:MAX_GENES_PER_DIRECTION]

        return {
            'gene_name': gene_name.upper(),
            'n_samples': n_samples,
            'n_sig': n_sig,
            'up_genes': [sym for sym, _ in up_sig],
            'down_genes': [sym for sym, _ in down_sig],
            'ks_scores': ks_dict,
            'p_values': p_dict,
            'fdr_values': fdr_dict,
            'all_genes': symbols,
            'all_ks': observed_ks.tolist(),
            'all_p': p_values.tolist(),
            'bootstrap_n': BOOTSTRAP_N,
            'fast_mode': fast_mode_used,
            'params': signature_params(),
        }

    def _bootstrap_null_ks(
        self,
        n_pool: int,
        n_sample: int,
        n_boot: int,
        exclude_cols: np.ndarray = None,
    ) -> np.ndarray:
        """
        从 shRNA 样本池（去掉目标基因自身样本列）中**无放回**抽取
        n_sample 个样本，重复 n_boot 次。
        """
        rank_matrix = self._shrna_rank_matrix  # (G, n_pool)
        G = rank_matrix.shape[0]
        null_ks = np.zeros((n_boot, G), dtype=np.float32)

        if exclude_cols is None:
            exclude_cols = np.array([], dtype=int)
        pool = np.setdiff1d(np.arange(n_pool), np.asarray(exclude_cols, dtype=int))
        if n_sample > len(pool):
            raise ValueError(
                f"Bootstrap 抽样池不足：需要 {n_sample} 个样本，"
                f"去掉目标基因样本后只剩 {len(pool)} 个"
            )

        batch_size = 500
        n_batches = (n_boot + batch_size - 1) // batch_size

        for b in range(n_batches):
            start = b * batch_size
            end = min(start + batch_size, n_boot)
            actual_batch = end - start

            for j in range(actual_batch):
                # 每次无放回抽样，且池中不含目标基因列
                idx = self._rng.choice(pool, n_sample, replace=False)
                sub = rank_matrix[:, idx]  # (G, n_sample)
                null_ks[start + j, :] = ks_uniform_batch(sub, G)

            if (b + 1) % 20 == 0 or b == n_batches - 1:
                print(f"[SignatureEngine] Bootstrap 进度: {end}/{n_boot}")

        return null_ks

    @staticmethod
    def _benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
        """
        BH 校正（FDR 控制）。
        """
        n = len(p_values)
        if n == 0:
            return p_values.copy()
        sorted_idx = np.argsort(p_values)
        sorted_p = p_values[sorted_idx]
        # BH：q_(i) = p_(i) * n / i，再自右向左取累计最小值
        bh_values = sorted_p * n / np.arange(1, n + 1)
        bh_values = np.minimum.accumulate(bh_values[::-1])[::-1]
        bh_values = np.clip(bh_values, 0, 1)
        result = np.empty(n, dtype=np.float64)
        result[sorted_idx] = bh_values
        return result

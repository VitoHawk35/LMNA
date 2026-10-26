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
from cache_manager import exclusive_file_lock, replace_file_with_retry
from config import (
    KS_THRESHOLD, FDR_THRESHOLD, BOOTSTRAP_N, RANDOM_SEED,
    CACHE_DIR, FAST_MODE_TOP_N, MAX_GENES_PER_DIRECTION,
    ALGO_VERSION, signature_params
)
from l3_robust_z import rank_columns_nanaware, RANK_NAN_SENTINEL
from suitability import (
    grade, load_annotation, loho_jaccard_min, precheck
)


# 可选的显式路径覆盖（仅测试/特殊部署使用）；生产默认走下方版本化路径。
_SHRNA_RANK_CACHE = None
_SHRNA_RANK_SHAPE = None


def _shrna_rank_cache_paths(n_shrna: int) -> tuple:
    """秩缓存路径：带算法版本与 shRNA 列数，数据/算法变化后自动失效。"""
    if _SHRNA_RANK_CACHE and _SHRNA_RANK_SHAPE:
        return _SHRNA_RANK_CACHE, _SHRNA_RANK_SHAPE
    stem = os.path.join(
        CACHE_DIR, f"_shrna_rank_matrix.v{ALGO_VERSION}.{n_shrna}"
    )
    return stem + ".dat", stem + ".shape.txt"


def _rank_cache_is_valid(cache_path: str, shape_path: str, shape: tuple) -> bool:
    if not (os.path.exists(cache_path) and os.path.exists(shape_path)):
        return False
    try:
        with open(shape_path, 'r', encoding='utf-8') as f:
            cached_shape = tuple(map(int, f.read().strip().split(',')))
    except (OSError, ValueError):
        return False
    if cached_shape != shape:
        return False
    try:
        # int16：每元素 2 字节，防止读到被截断的文件。
        return os.path.getsize(cache_path) == shape[0] * shape[1] * 2
    except OSError:
        return False


def _load_rank_cache(cache_path: str, shape: tuple) -> np.ndarray:
    return np.memmap(cache_path, dtype='int16', mode='r', shape=shape)


def _ensure_shrna_rank_cache(provider: IDataProvider) -> np.ndarray:
    """
    懒加载并缓存所有 shRNA 样本的列内排名矩阵。
    缓存为 numpy memmap 文件，文件名带 ALGO_VERSION 与 shRNA 列数；
    构建前对 <缓存文件>.lock 加排他锁，并在拿到锁后双重检查。
    """
    shrna_df = provider.get_all_shrna_samples()
    n_shrna = len(shrna_df)
    n_genes = len(provider.get_gene_symbols())
    shape = (n_genes, n_shrna)

    cache_path, shape_path = _shrna_rank_cache_paths(n_shrna)

    if _rank_cache_is_valid(cache_path, shape_path, shape):
        print(f"[SignatureEngine] 从缓存加载 shRNA 排名矩阵: {shape}")
        return _load_rank_cache(cache_path, shape)

    with exclusive_file_lock(cache_path + ".lock"):
        # 双重检查：等待锁期间别的进程可能已经构建完成。
        if _rank_cache_is_valid(cache_path, shape_path, shape):
            print(f"[SignatureEngine] 从缓存加载 shRNA 排名矩阵（等待锁后）: {shape}")
            return _load_rank_cache(cache_path, shape)

        print(f"[SignatureEngine] 首次构建 shRNA 排名矩阵 ({n_shrna} 样本)...")
        sig_ids = shrna_df['sig_id'].tolist()

        # 分块读取并计算排名，避免一次性加载大矩阵
        CHUNK = 5000
        rank_chunks = []
        for start in range(0, n_shrna, CHUNK):
            end = min(start + CHUNK, n_shrna)
            chunk_sigs = sig_ids[start:end]
            expr_chunk = provider.get_expression_matrix(chunk_sigs)
            # 列内降序排名：1=最高，978=最低。
            # L7e：NaN（L3 MAD=0 基因）不参与排名、配哨兵秩 0；
            # 无 NaN 的数据（L5/fixture）与旧口径逐元素一致。
            ranks = rank_columns_nanaware(expr_chunk)
            rank_chunks.append(ranks)
            print(f"[SignatureEngine] 排名计算进度: {end}/{n_shrna}")

        rank_matrix = np.hstack(rank_chunks)

        # 写入临时 memmap，完整落盘后原子替换，避免并发读到半截文件。
        tmp_cache = f"{cache_path}.tmp.{os.getpid()}"
        tmp_shape = f"{shape_path}.tmp.{os.getpid()}"
        try:
            fp = np.memmap(
                tmp_cache, dtype='int16', mode='w+', shape=rank_matrix.shape
            )
            fp[:] = rank_matrix[:]
            fp.flush()
            del fp
            with open(tmp_shape, 'w', encoding='utf-8') as f:
                f.write(f"{rank_matrix.shape[0]},{rank_matrix.shape[1]}")
            replace_file_with_retry(tmp_cache, cache_path)
            replace_file_with_retry(tmp_shape, shape_path)
        finally:
            for tmp in (tmp_cache, tmp_shape):
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass

    return _load_rank_cache(cache_path, shape)


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
        # landmark 基因 symbol -> 行下标（用于 L3 的敲低效率参考信息）
        self._symbol_upper_index = {
            str(sym).strip().upper(): i
            for i, sym in enumerate(self._shrna_gene_symbols)
        }
        # L7e：NaN 剔除口径。秩矩阵中哨兵秩 0 = 该样本该基因为 NaN
        # （L3 MAD=0 板）。某个基因只要在 null 池任一实例中为 NaN，
        # 其 null 分布即被污染（哨兵秩会造成假性 KS），签名中一律剔除。
        # 无 NaN 的数据（L5/fixture）此处为 None，行为与旧版完全一致。
        if bool((self._shrna_rank_matrix == RANK_NAN_SENTINEL).any()):
            self._pool_nan_invalid = np.asarray(
                (self._shrna_rank_matrix == RANK_NAN_SENTINEL).any(axis=1)
            )
            n_bad = int(self._pool_nan_invalid.sum())
            print(f"[SignatureEngine] null 池含 NaN 基因 {n_bad} 个，"
                  f"签名计算时将剔除并计数")
        else:
            self._pool_nan_invalid = None
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

        # 2. 样本内排名（L7e：NaN 不进秩签名，配哨兵秩 0；
        #    无 NaN 时与旧口径逐元素一致）
        target_ranks = rank_columns_nanaware(target_expr)

        # 3. 计算观测 KS 分数（G 由数据推导）
        G = self._n_genes
        observed_ks = ks_uniform_batch(target_ranks, G)

        # 3b. L7e NaN 剔除：基因在 null 池任一实例或目标任一样本中为 NaN
        # （哨兵秩 0）→ 其 KS/p/FDR 不可靠，从签名中剔除（计数入结果）。
        # 剔除基因的 KS 置 0，保证不进 up/down、不进 LOHO top 集。
        invalid = (target_ranks == RANK_NAN_SENTINEL).any(axis=1)
        if self._pool_nan_invalid is not None:
            invalid = invalid | self._pool_nan_invalid
        excluded_nan_genes = []
        if bool(invalid.any()):
            excluded_nan_genes = sorted(
                str(self._shrna_gene_symbols[i])
                for i in np.flatnonzero(invalid)
            )
            observed_ks = observed_ks.copy()
            observed_ks[invalid] = 0.0

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

        # 6. BH 校正（L7e：被剔除的 NaN 基因不参与校正——其 p 值由
        #    哨兵秩算出，混进 BH 会抬高其他基因的校正门槛）
        if bool(invalid.any()):
            fdr_values = np.ones(G, dtype=np.float64)
            valid_idx = np.flatnonzero(~invalid)
            fdr_values[valid_idx] = self._benjamini_hochberg(
                p_values[valid_idx])
        else:
            fdr_values = self._benjamini_hochberg(p_values)

        # 7. 筛选签名基因
        symbols = self._shrna_gene_symbols
        up_sig = []    # (symbol, ks)，ks > 0
        down_sig = []  # (symbol, ks)，ks < 0
        ks_dict = {}
        p_dict = {}
        fdr_dict = {}

        for i, sym in enumerate(symbols):
            if invalid[i]:
                # 剔除基因：结果置 null（JSON null），不进 up/down
                ks_dict[sym] = None
                p_dict[sym] = None
                fdr_dict[sym] = None
                continue
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

        up_genes = [sym for sym, _ in up_sig]
        down_genes = [sym for sym, _ in down_sig]
        gene_upper = gene_name.strip().upper()

        # L3：敲低效率参考信息（只在靶基因是 landmark 时有值）。
        # 取靶基因在目标样本上的中位 z；L7e：NaN（MAD=0）不参与中位数。
        target_idx = self._symbol_upper_index.get(gene_upper)
        target_median_z = None
        if target_idx is not None and target_expr.shape[1] > 0:
            row_vals = target_expr[target_idx, :]
            if np.isnan(row_vals).any():
                finite = row_vals[np.isfinite(row_vals)]
                target_median_z = (
                    float(np.median(finite)) if finite.size else None
                )
            else:
                target_median_z = float(np.median(row_vals))

        # L3：LOHO Jaccard。k = max(10, 封顶后的 up + down 数量)。
        # L7e：gene_valid_mask 把被剔除的 NaN 基因挡在 top 集之外。
        loho_k = max(10, len(up_genes) + len(down_genes))
        full_top = np.argsort(-np.abs(observed_ks))[:min(loho_k, G)]
        hairpin_ids = (
            target_df['pert_id'].astype(str).tolist()
            if 'pert_id' in target_df.columns
            else [str(i) for i in range(n_samples)]
        )
        loho, loho_detail = loho_jaccard_min(
            ranks=target_ranks,
            hairpin_ids=hairpin_ids,
            full_top_indices=full_top,
            G=G,
            k=loho_k,
            gene_valid_mask=(~invalid) if bool(invalid.any()) else None,
        )

        pre = precheck(self.provider, gene_upper)

        # 剔除基因在 all_ks/all_p 中置 null（JSON null），避免哨兵秩
        # 算出的伪 KS/p 被下游误读。
        if bool(invalid.any()):
            all_ks = [None if invalid[i] else float(observed_ks[i])
                      for i in range(G)]
            all_p = [None if invalid[i] else float(p_values[i])
                     for i in range(G)]
        else:
            all_ks = observed_ks.tolist()
            all_p = p_values.tolist()

        signature = {
            'gene_name': gene_upper,
            'n_samples': n_samples,
            'n_sig': n_sig,
            'up_genes': up_genes,
            'down_genes': down_genes,
            'ks_scores': ks_dict,
            'p_values': p_dict,
            'fdr_values': fdr_dict,
            'all_genes': symbols,
            'all_ks': all_ks,
            'all_p': all_p,
            'bootstrap_n': BOOTSTRAP_N,
            'fast_mode': fast_mode_used,
            'params': signature_params(),
            # L3 新增字段（旧缓存没有这些字段时 API 给默认值）
            'n_hairpins': pre['n_hairpins'],
            'n_cells': pre['n_cells'],
            'loho_jaccard_min': loho,
            'loho_detail': loho_detail,
            'target_median_z': target_median_z,
            # L7e：MAD=0 剔除基因（NaN 不进秩签名的口径结果）
            'excluded_nan_genes': excluded_nan_genes,
            'n_excluded_nan_genes': len(excluded_nan_genes),
        }

        annotation, annotation_reason = load_annotation(gene_upper)
        signature['qc'] = grade(
            signature,
            pre,
            annotation=annotation,
            annotation_reason=annotation_reason,
        )
        return signature

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

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
药物打分器
支持 XSUM 和 WTCS 两种算法
使用药物中位数矩阵缓存加速。

L4：XSUM 增加药物级随机签名 null —— 单侧 p 值、BH-FDR 与 null z。

统一符号约定（务必与任务文件保持一致）：
    mimic = Σz(up) − Σz(down)     正 = 药物模拟（mimic）查询签名
    score = −mimic                高分 = 逆转（reversal）
    mode = "lof"（默认）          找逆转药：top 按 fdr_reversal 升序、score 降序
    mode = "gof"                  找模拟药：top 按 fdr_mimic 升序、score 升序
"""

import numpy as np
import pandas as pd
from typing import Dict

from data_provider import IDataProvider
from config import DEFAULT_TOP_K, DEFAULT_BOTTOM_K, DRUG_NULL_N, RANDOM_SEED
from drug_median_cache import get_drug_median_matrix
from signature_engine import SignatureEngine


# top/bottom 展示用的数值精度（all_scores 保留原始精度）
_P_DIGITS = 6
_Z_DIGITS = 4


def _round_optional(value, ndigits: int):
    """四舍五入；None/NaN 原样返回 None（WTCS 没有 null 统计，字段为 None）。"""
    if value is None or pd.isna(value):
        return None
    return round(float(value), ndigits)


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
        bottom_k: int = DEFAULT_BOTTOM_K,
        mode: str = "lof",
    ) -> Dict:
        """
        用指定方法对药物进行打分。

        mode:
            "lof"（默认）：关注逆转药，top 为逆转方向；
            "gof"：关注模拟药，top 为模拟方向。
        WTCS 没有 null 统计字段，mode 只影响列表按 score 的排序方向。
        """
        method = method.lower()
        mode = (mode or "lof").lower()
        if mode not in ("lof", "gof"):
            raise ValueError(f"不支持的 mode: {mode}（只能是 lof 或 gof）")

        if method == "xsum":
            return self._xsum_score(signature, top_k, bottom_k, mode)
        elif method == "wtcs":
            return self._wtcs_score(signature, top_k, bottom_k, mode)
        else:
            raise ValueError(f"不支持的打分方法: {method}")

    # ------------------------------------------------------------------
    # 药物级随机签名 null
    # ------------------------------------------------------------------

    def drug_null(
        self,
        up_idx,
        down_idx,
        M: int = DRUG_NULL_N,
        batch: int = 500,
        seed: int = RANDOM_SEED,
    ) -> Dict:
        """
        用 M 个同样大小的随机签名估计每个药物的经验 null 分布。

        随机签名：从 G 个基因中无放回抽 len(up)+len(down) 个，前 len(up) 个
        记 +1、其余记 −1，得到权重向量 W；null = W @ D。

        观测值按统一约定：
            obs_mimic = Σz(up) − Σz(down)（正 = 模拟）
            p_mimic   = (#{null >= obs_mimic} + 1) / (M + 1)   （单侧，上尾）
            p_reversal= (#{null <= obs_mimic} + 1) / (M + 1)   （单侧，下尾）
            null_z    = (obs_mimic − mean(null)) / sd(null)

        FDR 用 L1 修复后的 Benjamini-Hochberg，分别在 p_mimic 与
        p_reversal 上对全部药物做校正（两个方向各自一套 FDR）。

        内存：逐批构造 (batch, G) 的权重矩阵和 (batch, n_drug) 的 null，
        不会一次性构造 (M, n_drug)。

        Returns:
            dict，数组长度均为 n_drug；另含 null_mean/null_sd/M/batch/seed 等元信息。
        """
        D = self._drug_matrix
        G, n_drug = int(D.shape[0]), int(D.shape[1])

        up_idx = np.asarray(up_idx, dtype=np.int64).ravel()
        down_idx = np.asarray(down_idx, dtype=np.int64).ravel()
        for name, idx in (("up_idx", up_idx), ("down_idx", down_idx)):
            if idx.size and (idx.min() < 0 or idx.max() >= G):
                raise ValueError(f"{name} 越界：基因索引应在 [0, {G}) 内")

        n_up = int(up_idx.size)
        n_down = int(down_idx.size)
        n_sample = n_up + n_down
        if n_sample > G:
            raise ValueError(
                f"随机签名大小 {n_sample}（up={n_up}, down={n_down}）超过基因数 G={G}"
            )
        if M <= 0:
            raise ValueError(f"M 必须为正整数，收到 {M}")
        if batch <= 0:
            raise ValueError(f"batch 必须为正整数，收到 {batch}")
        M = int(M)
        batch = min(int(batch), M)

        # 观测 mimic（用 float64 累加，避免大签名下的精度损失）
        obs_mimic = np.zeros(n_drug, dtype=np.float64)
        if n_up:
            obs_mimic += np.asarray(D[up_idx].sum(axis=0), dtype=np.float64).ravel()
        if n_down:
            obs_mimic -= np.asarray(D[down_idx].sum(axis=0), dtype=np.float64).ravel()
        # 与 float32 的 null 比较时保持同 dtype，避免每批生成 float64 临时数组
        obs_cmp = obs_mimic.astype(np.float32)

        ge = np.zeros(n_drug, dtype=np.int64)       # null >= obs
        le = np.zeros(n_drug, dtype=np.int64)       # null <= obs
        sum_null = np.zeros(n_drug, dtype=np.float64)
        sum_sq = np.zeros(n_drug, dtype=np.float64)

        rng = np.random.default_rng(seed)
        done = 0
        while done < M:
            b = min(batch, M - done)

            if n_sample == 0:
                # 空签名：null 恒为 0
                null = np.zeros((b, n_drug), dtype=np.float32)
            else:
                # 每行独立无放回抽样：random + argpartition，避免 Python 循环
                keys = rng.random((b, G))
                chosen = np.argpartition(keys, n_sample - 1, axis=1)[:, :n_sample]

                W = np.zeros((b, G), dtype=np.float32)
                if n_up:
                    W[np.repeat(np.arange(b), n_up), chosen[:, :n_up].ravel()] = 1.0
                if n_down:
                    W[np.repeat(np.arange(b), n_down), chosen[:, n_up:].ravel()] = -1.0

                null = np.asarray(W @ D, dtype=np.float32)
                del W, keys, chosen

            ge += np.count_nonzero(null >= obs_cmp, axis=0)
            le += np.count_nonzero(null <= obs_cmp, axis=0)
            sum_null += null.sum(axis=0, dtype=np.float64)
            sum_sq += np.einsum("ij,ij->j", null, null, dtype=np.float64)
            done += b

        denom = float(M + 1)
        p_mimic = (ge.astype(np.float64) + 1.0) / denom
        p_reversal = (le.astype(np.float64) + 1.0) / denom

        # 复用 L1 修复后的 BH（与 scipy.stats.false_discovery_control 等价）
        fdr_mimic = SignatureEngine._benjamini_hochberg(p_mimic)
        fdr_reversal = SignatureEngine._benjamini_hochberg(p_reversal)

        null_mean = sum_null / float(M)
        null_var = np.maximum(sum_sq / float(M) - null_mean ** 2, 0.0)
        null_sd = np.sqrt(null_var)
        null_z = np.zeros(n_drug, dtype=np.float64)
        np.divide(obs_mimic - null_mean, null_sd, out=null_z, where=null_sd > 0)

        return {
            "obs_mimic": obs_mimic,
            "p_mimic": p_mimic,
            "p_reversal": p_reversal,
            "fdr_mimic": fdr_mimic,
            "fdr_reversal": fdr_reversal,
            "null_z": null_z,
            "null_mean": null_mean,
            "null_sd": null_sd,
            "M": M,
            "batch": batch,
            "seed": int(seed),
            "n_up": n_up,
            "n_down": n_down,
        }

    # ------------------------------------------------------------------
    # XSUM / WTCS
    # ------------------------------------------------------------------

    def _xsum_score(
        self, signature: Dict, top_k: int, bottom_k: int, mode: str = "lof"
    ) -> Dict:
        """XSUM 算法（含药物级 null 的 p 值 / FDR）。"""
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

        null_stats = self.drug_null(up_indices, down_indices)

        df = pd.DataFrame({
            "drug_name": self._drug_names,
            "score": score_vec,
            "p_reversal": null_stats["p_reversal"],
            "fdr_reversal": null_stats["fdr_reversal"],
            "p_mimic": null_stats["p_mimic"],
            "fdr_mimic": null_stats["fdr_mimic"],
            "null_z": null_stats["null_z"],
        })
        # all_scores 仍按 score 降序（保持原有对外行为）
        df = df.sort_values("score", ascending=False).reset_index(drop=True)

        if mode == "lof":
            # 逆转药：FDR 升序，再 score 降序
            top = df.sort_values(
                ["fdr_reversal", "score"], ascending=[True, False]
            ).head(top_k)
            # 模拟药：FDR 升序，再 score 升序（对称方向）
            bottom = df.sort_values(
                ["fdr_mimic", "score"], ascending=[True, True]
            ).head(bottom_k)
        else:
            # gof：模拟药：FDR 升序，再 score 升序
            top = df.sort_values(
                ["fdr_mimic", "score"], ascending=[True, True]
            ).head(top_k)
            # 逆转药：FDR 升序，再 score 降序
            bottom = df.sort_values(
                ["fdr_reversal", "score"], ascending=[True, False]
            ).head(bottom_k)

        return {
            "method": "xsum",
            "mode": mode,
            "gene_name": signature["gene_name"],
            "n_up_genes": len(up_genes),
            "n_down_genes": len(down_genes),
            "null_params": {
                "M": null_stats["M"],
                "batch": null_stats["batch"],
                "seed": null_stats["seed"],
            },
            "top_drugs": self._drug_records(top),
            "bottom_drugs": self._drug_records(bottom),
            "all_scores": df.to_dict("records"),
        }

    def _wtcs_score(
        self, signature: Dict, top_k: int, bottom_k: int, mode: str = "lof"
    ) -> Dict:
        """WTCS 算法（没有药物级 null，p/FDR/null_z 字段为 None）。"""
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
            "score": score_vec,
            "p_reversal": None,
            "fdr_reversal": None,
            "p_mimic": None,
            "fdr_mimic": None,
            "null_z": None,
        })
        df = df.sort_values("score", ascending=False).reset_index(drop=True)

        max_abs = df["score"].abs().max()
        if max_abs > 0:
            df["score"] = df["score"] / max_abs

        if mode == "lof":
            top = df.head(top_k)
            bottom = df.tail(bottom_k).iloc[::-1]
        else:
            top = df.tail(top_k).iloc[::-1]
            bottom = df.head(bottom_k)

        return {
            "method": "wtcs",
            "mode": mode,
            "gene_name": signature["gene_name"],
            "n_up_genes": len(up_genes),
            "n_down_genes": len(down_genes),
            "null_params": None,
            "top_drugs": self._drug_records(top),
            "bottom_drugs": self._drug_records(bottom),
            "all_scores": df.to_dict("records"),
        }

    @staticmethod
    def _drug_records(df: pd.DataFrame) -> list:
        """把 top/bottom DataFrame 转成对外的记录列表（p/FDR 保留 6 位）。"""
        records = []
        for _, row in df.iterrows():
            records.append({
                "drug_name": row["drug_name"],
                "score": round(float(row["score"]), 4),
                "p_reversal": _round_optional(row.get("p_reversal"), _P_DIGITS),
                "fdr_reversal": _round_optional(row.get("fdr_reversal"), _P_DIGITS),
                "p_mimic": _round_optional(row.get("p_mimic"), _P_DIGITS),
                "fdr_mimic": _round_optional(row.get("fdr_mimic"), _P_DIGITS),
                "null_z": _round_optional(row.get("null_z"), _Z_DIGITS),
            })
        return records

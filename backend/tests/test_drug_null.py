#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L4：药物级随机签名 null → p 值 / FDR。

符号约定（与 deliveries/task-L4.md 一致）：
    mimic = Σz(up) − Σz(down)      正 = 药物模拟（mimic）查询签名
    score = −mimic                 高分 = 逆转（reversal）
    p_mimic    = (#{null >= obs} + 1) / (M + 1)   单侧上尾
    p_reversal = (#{null <= obs} + 1) / (M + 1)   单侧下尾
"""

import gc
import os
import tracemalloc

import numpy as np
import pytest
from scipy import stats
from scipy.stats import false_discovery_control

import config
from drug_scorer import DrugScorer


G = 978
N_UP = 25
N_DOWN = 25
NULL_FIELDS = ("p_reversal", "fdr_reversal", "p_mimic", "fdr_mimic", "null_z")


class _StubProvider:
    """只提供 get_gene_symbols 的最小 provider（XSUM/WTCS 打分用）。"""

    def __init__(self, symbols):
        self._symbols = list(symbols)

    def get_gene_symbols(self):
        return list(self._symbols)


def _scorer_with_matrix(matrix, names=None):
    """绕过 provider/缓存，直接注入药物矩阵（纯数组测试用）。"""
    scorer = object.__new__(DrugScorer)
    scorer._drug_matrix = matrix
    scorer._drug_names = names or [f"drug_{i}" for i in range(matrix.shape[1])]
    return scorer


def _synthetic_case(seed=0, n_drug=201):
    """G=978、n_drug-1 个随机药物 + 1 个完美逆转药。"""
    rng = np.random.default_rng(seed)
    matrix = rng.standard_normal((G, n_drug)).astype(np.float32)
    up = rng.choice(G, N_UP, replace=False)
    down = rng.choice(np.setdiff1d(np.arange(G), up), N_DOWN, replace=False)

    perfect = n_drug - 1
    matrix[:, perfect] = 0.0
    # 对 up 基因下调、对 down 基因上调 → mimic = −(N_UP+N_DOWN)，完美逆转
    matrix[up, perfect] = -1.0
    matrix[down, perfect] = 1.0
    return _scorer_with_matrix(matrix), up, down, perfect


# ---------------------------------------------------------------------------
# 合成数据：null 分布、p 值方向、FDR
# ---------------------------------------------------------------------------

def test_null_distribution_and_p_value_ranges():
    scorer, up, down, _ = _synthetic_case()
    M = 1000
    result = scorer.drug_null(up, down, M=M, batch=250, seed=42)

    n_drug = scorer._drug_matrix.shape[1]
    for key in ("p_mimic", "p_reversal", "fdr_mimic", "fdr_reversal", "null_z"):
        assert result[key].shape == (n_drug,)
        assert np.all(np.isfinite(result[key]))

    lo = 1.0 / (M + 1)
    for key in ("p_mimic", "p_reversal"):
        assert result[key].min() >= lo - 1e-15
        assert result[key].max() <= 1.0
    for key in ("fdr_mimic", "fdr_reversal"):
        assert result[key].min() >= 0.0
        assert result[key].max() <= 1.0
        # BH 校正后不小于原始 p
        p_key = "p_" + key.split("_", 1)[1]
        assert np.all(result[key] >= result[p_key] - 1e-12)

    # 随机高斯药物列：null 均值≈0（M=1000 时均值标准误≈7.07/√1000≈0.22）、
    # sd≈sqrt(N_UP+N_DOWN)
    assert np.max(np.abs(result["null_mean"][:20])) < 1.0
    assert np.allclose(result["null_sd"][:20], np.sqrt(N_UP + N_DOWN), rtol=0.15)

    # 完美逆转药：obs 远低于 null → p_reversal 最小、z 很负
    assert result["null_z"][-1] < -10
    assert result["p_reversal"][-1] == pytest.approx(1.0 / (M + 1), rel=0.5)


def test_random_drugs_p_reversal_is_uniform():
    """随机药物的 p_reversal 应近似 U(0,1)（验收：KS 检验 p > 0.01，M=2000）。"""
    scorer, up, down, _ = _synthetic_case()
    result = scorer.drug_null(up, down, M=2000, batch=500, seed=42)
    p_random = result["p_reversal"][:-1]  # 去掉完美逆转药

    ks_rev = stats.kstest(p_random, "uniform")
    assert ks_rev.pvalue > 0.01, f"p_reversal 偏离均匀分布: {ks_rev}"
    ks_mim = stats.kstest(result["p_mimic"][:-1], "uniform")
    assert ks_mim.pvalue > 0.01, f"p_mimic 偏离均匀分布: {ks_mim}"


def test_perfect_reversal_drug_has_small_fdr():
    """
    完美逆转药 fdr_reversal < 0.01。

    注：全局 BH 在 n_drug=201、M=2000 时最小可达 FDR 约为 201/2001≈0.1，
    因此本用例用 M=30000（201/30001≈0.0067）验证该验收阈值；M=2000 仅用于
    上面的 KS 检验。详见 deliveries/task-L4.md。
    """
    scorer, up, down, perfect = _synthetic_case()
    M = 30000
    result = scorer.drug_null(up, down, M=M, batch=500, seed=42)

    assert result["p_reversal"][perfect] <= 5.0 / (M + 1)
    assert result["null_z"][perfect] < -5
    assert result["fdr_reversal"][perfect] < 0.01
    # 完美药是 p_reversal 最小的药（并列时允许按索引排在其后）
    assert int(np.argmin(result["p_reversal"])) == perfect


def test_fdr_matches_scipy_bh_and_is_monotone():
    scorer, up, down, _ = _synthetic_case()
    result = scorer.drug_null(up, down, M=1000, batch=200, seed=11)

    for tail in ("mimic", "reversal"):
        p = result[f"p_{tail}"]
        fdr = result[f"fdr_{tail}"]
        ref = false_discovery_control(p, method="bh")
        assert np.max(np.abs(fdr - ref)) < 1e-12

        order = np.argsort(p)
        assert np.all(np.diff(fdr[order]) >= -1e-12), "FDR 应随 p 单调不减"


def test_batched_matches_single_batch():
    """相同 seed/M 下，分批与单批的计数应完全一致（RNG 流不随分块改变）。"""
    scorer, up, down, _ = _synthetic_case()
    batched = scorer.drug_null(up, down, M=1000, batch=100, seed=7)
    single = scorer.drug_null(up, down, M=1000, batch=1000, seed=7)

    for key in ("p_mimic", "p_reversal", "fdr_mimic", "fdr_reversal"):
        assert np.array_equal(batched[key], single[key])
    assert np.allclose(batched["null_mean"], single["null_mean"], atol=1e-12)
    assert np.allclose(batched["null_sd"], single["null_sd"], atol=1e-9)


def test_empty_and_invalid_signatures():
    scorer, _, _, _ = _synthetic_case(n_drug=5)

    result = scorer.drug_null([], [], M=50, batch=10, seed=1)
    assert np.all(result["p_mimic"] == 1.0)
    assert np.all(result["p_reversal"] == 1.0)
    assert np.all(result["null_z"] == 0.0)

    with pytest.raises(ValueError):
        scorer.drug_null(list(range(G + 1)), [], M=10)
    with pytest.raises(ValueError):
        scorer.drug_null([0], [1], M=0)
    with pytest.raises(ValueError):
        scorer.drug_null([0], [1], M=10, batch=0)


def test_20k_drugs_peak_memory_under_1gb():
    """2 万药物规模下峰值内存 < 1GB（不在内存中构造 (M, n_drug)）。"""
    n_drug = 20000
    rng = np.random.default_rng(0)
    up = rng.choice(G, 50, replace=False)
    down = rng.choice(np.setdiff1d(np.arange(G), up), 50, replace=False)

    gc.collect()
    tracemalloc.start()
    try:
        matrix = rng.standard_normal((G, n_drug), dtype=np.float32)
        scorer = _scorer_with_matrix(matrix)
        result = scorer.drug_null(up, down, M=20, batch=10, seed=1)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert result["p_reversal"].shape == (n_drug,)
    assert peak < 1024 ** 3, f"峰值内存 {peak / 1e6:.1f} MB 超过 1GB"


def test_xsum_output_fields_and_mode_sorting():
    """XSUM 每条记录新增 p/FDR 字段；lof 按 fdr_reversal、gof 按 fdr_mimic 排序。"""
    n_drug = 30
    scorer, up, down, perfect = _synthetic_case(n_drug=n_drug)
    symbols = [f"G{i}" for i in range(G)]
    scorer.provider = _StubProvider(symbols)
    sig = {
        "gene_name": "TEST",
        "up_genes": [symbols[i] for i in up],
        "down_genes": [symbols[i] for i in down],
    }

    lof = scorer.score_drugs(sig, method="xsum", top_k=5, bottom_k=5, mode="lof")
    assert lof["mode"] == "lof"
    assert lof["null_params"]["M"] == config.DRUG_NULL_N
    assert lof["top_drugs"][0]["drug_name"] == f"drug_{perfect}"
    for record in lof["top_drugs"] + lof["bottom_drugs"] + lof["all_scores"]:
        assert set(NULL_FIELDS).issubset(record.keys())
        assert record["p_reversal"] is not None
    # lof top：fdr_reversal 升序（展示值保留 6 位，同值区间内不再校验 score 次序）
    fdr_rev = [r["fdr_reversal"] for r in lof["top_drugs"]]
    assert all(a <= b for a, b in zip(fdr_rev, fdr_rev[1:]))

    gof = scorer.score_drugs(sig, method="xsum", top_k=90, bottom_k=5, mode="gof")
    assert gof["mode"] == "gof"
    assert gof["top_drugs"][0]["drug_name"] != f"drug_{perfect}"
    fdr_mim = [r["fdr_mimic"] for r in gof["top_drugs"]]
    assert all(a <= b for a, b in zip(fdr_mim, fdr_mim[1:]))

    wtcs = scorer.score_drugs(sig, method="wtcs", top_k=5, bottom_k=5)
    for record in wtcs["top_drugs"] + wtcs["bottom_drugs"] + wtcs["all_scores"]:
        for key in NULL_FIELDS:
            assert record[key] is None

    with pytest.raises(ValueError):
        scorer.score_drugs(sig, method="xsum", mode="sideways")


# ---------------------------------------------------------------------------
# 夹具：已知抑制剂（验收：CDK4/EGFR/MTOR 至少一个 fdr_mimic < 0.05）
# ---------------------------------------------------------------------------

def _fixture_available():
    fixture_dir = os.getenv("LMNA_FIXTURE_DIR")
    if not fixture_dir or not os.path.isdir(fixture_dir):
        return False
    return all(
        os.path.exists(os.path.join(fixture_dir, name))
        for name in (
            "lmna_fixture.npz",
            "lmna_fixture_sh.tsv",
            "lmna_fixture_cp.tsv",
            "lmna_fixture_meta.json",
        )
    )


requires_fixture = pytest.mark.skipif(
    not _fixture_available(), reason="未设置 LMNA_FIXTURE_DIR 或夹具不完整"
)


@pytest.fixture(scope="module")
def fixture_null_results():
    """夹具上为 CDK4/EGFR/MTOR 计算签名并跑 M=10000 的药物级 null。"""
    from fixture_provider import FixtureProvider
    from signature_engine import SignatureEngine

    provider = FixtureProvider()
    scorer = DrugScorer(provider)
    engine = SignatureEngine(provider)
    symbol_to_idx = {
        symbol: i for i, symbol in enumerate(provider.get_gene_symbols())
    }

    results = {}
    for target in ("CDK4", "EGFR", "MTOR"):
        signature = engine.compute_signature(target)
        up_idx = [symbol_to_idx[g] for g in signature["up_genes"] if g in symbol_to_idx]
        down_idx = [
            symbol_to_idx[g] for g in signature["down_genes"] if g in symbol_to_idx
        ]
        results[target] = (
            scorer.drug_null(
                up_idx, down_idx, M=10000, batch=500, seed=config.RANDOM_SEED
            ),
            up_idx,
            down_idx,
        )
    return provider, scorer, results


@requires_fixture
def test_fixture_known_inhibitor_fdr_mimic_small(fixture_null_results):
    """
    已知抑制剂应位于 mimic 端（fdr_mimic 小、p_reversal≈1）。

    验收：CDK4、EGFR、MTOR 至少有一个已知抑制剂 fdr_mimic < 0.05。
    """
    provider, scorer, results = fixture_null_results
    drug_index = {name: i for i, name in enumerate(scorer._drug_names)}

    for target, (result, _, _) in results.items():
        inhibitors = [
            name
            for name in provider.meta["targets"][target]["inhibitors"]
            if name in drug_index
        ]
        assert inhibitors, f"{target} 的已知抑制剂都不在夹具药物表中"

        best = min(inhibitors, key=lambda name: result["fdr_mimic"][drug_index[name]])
        fdr = float(result["fdr_mimic"][drug_index[best]])
        p_mimic = float(result["p_mimic"][drug_index[best]])
        p_reversal = float(result["p_reversal"][drug_index[best]])

        assert fdr < 0.05, f"{target} 最佳抑制剂 {best} fdr_mimic={fdr:.4g}"
        assert p_mimic < 0.05
        # 方向检查：抑制剂模拟敲低，不应落在逆转尾
        assert p_reversal > 0.95


@requires_fixture
def test_fixture_fdr_matches_scipy(fixture_null_results):
    _, _, results = fixture_null_results
    for target, (result, _, _) in results.items():
        for tail in ("mimic", "reversal"):
            ref = false_discovery_control(result[f"p_{tail}"], method="bh")
            assert np.max(np.abs(result[f"fdr_{tail}"] - ref)) < 1e-12, target

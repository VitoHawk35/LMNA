#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L1 签名与打分算法的纯数学/接口测试（不依赖夹具的部分）。"""

import os

import numpy as np
import pandas as pd
import pytest

import config
import signature_engine as se
import task_queue
from data_provider import IDataProvider
from signature_engine import SignatureEngine, ks_uniform_batch


# ---------------------------------------------------------------------------
# KS 符号 / G 推导
# ---------------------------------------------------------------------------

def test_ks_sign_upregulated_is_positive():
    """基因在所有样本里秩都是 1（表达最高）→ KS > 0.9 → 属于 up_genes。"""
    rng = np.random.default_rng(0)
    ranks = rng.integers(2, 979, size=(978, 20)).astype(np.int16)
    ranks[0, :] = 1
    scores = ks_uniform_batch(ranks, 978)
    assert scores[0] > 0.9


def test_ks_sign_downregulated_is_negative():
    rng = np.random.default_rng(0)
    ranks = rng.integers(1, 978, size=(978, 20)).astype(np.int16)
    ranks[0, :] = 978
    scores = ks_uniform_batch(ranks, 978)
    assert scores[0] < -0.9


def test_ks_uniform_batch_requires_G():
    with pytest.raises(TypeError):
        ks_uniform_batch(np.ones((1, 5), dtype=np.int16))


# ---------------------------------------------------------------------------
# BH 校正
# ---------------------------------------------------------------------------

def test_bh_matches_scipy():
    from scipy.stats import false_discovery_control

    rng = np.random.default_rng(123)
    cases = [
        rng.uniform(size=100),
        np.array([0.01, 0.04, 0.03, 0.5]),
        np.array([1.0, 0.5, 0.5, 0.2, 0.0]),
        np.array([1e-6, 1e-6, 1e-6] + [1.0] * 5),
    ]
    for p in cases:
        q = SignatureEngine._benjamini_hochberg(p)
        ref = false_discovery_control(p, method="bh")
        assert np.max(np.abs(q - ref)) < 1e-12


def test_bh_noise_plus_three_signals():
    """975 个 U(0,1) 噪声 + 3 个 p=1e-6 → q<0.05 的个数必须远小于 978。"""
    rng = np.random.default_rng(7)
    p = np.concatenate([rng.uniform(size=975), np.full(3, 1e-6)])
    q = SignatureEngine._benjamini_hochberg(p)
    assert np.sum(q < 0.05) <= 10


# ---------------------------------------------------------------------------
# 假 provider / engine 工厂
# ---------------------------------------------------------------------------

class _ArrayProvider(IDataProvider):
    """内存 provider：expr 形状 (G, n_sig)，sh_df 给出每个 sig_id 的注释。"""

    def __init__(self, expr, sh_df, symbols):
        self.expr = np.asarray(expr, dtype=np.float32)
        self.sh_df = sh_df
        self.symbols = list(symbols)
        self.sig_ids = sh_df["sig_id"].tolist()
        self._sig_to_idx = {s: i for i, s in enumerate(self.sig_ids)}

    def get_shrna_samples(self, gene_name):
        mask = (
            self.sh_df["pert_iname"].fillna("").astype(str).str.upper()
            == gene_name.strip().upper()
        )
        return self.sh_df[mask].copy()

    def get_all_shrna_samples(self):
        return self.sh_df.copy()

    def get_expression_matrix(self, sig_ids):
        idx = [self._sig_to_idx[s] for s in sig_ids]
        return self.expr[:, idx].copy()

    def get_gene_symbols(self):
        return list(self.symbols)

    def get_drug_samples(self):
        return pd.DataFrame({"sig_id": []})

    def get_drug_expression_matrix(self, sig_ids):
        return self.expr[:, [self._sig_to_idx[s] for s in sig_ids]].copy()

    def get_lm_gene_indices(self):
        return np.arange(len(self.symbols))

    def get_vehicle_samples_for_plate(self, plate_id):
        raise NotImplementedError

    def list_available_genes(self):
        return ["G0"]

    def get_drug_name_map(self):
        return pd.Series(dtype=object)


def _make_provider(n_genes=20, n_target=10, n_pool=30, target="G0"):
    """目标样本列里 gene_i 恒定排第 i+1；pool 列里换成另一种排列。"""
    symbols = [f"G{i}" for i in range(n_genes)]
    n_sig = n_target + n_pool
    expr = np.zeros((n_genes, n_sig), dtype=np.float32)

    # 目标样本：所有列相同 → gene_i 秩恒为 i+1
    for j in range(n_target):
        expr[:, j] = -np.arange(n_genes)

    # pool：gene0 排第 2（确保其 null KS 严格小于观测值），gene1 排第 1
    for j in range(n_target, n_sig):
        expr[1, j] = 10.0
        expr[0, j] = 9.0
        expr[2:, j] = -np.arange(2, n_genes)

    rows = []
    for j in range(n_sig):
        rows.append({
            "sig_id": f"S{j:03d}",
            "pert_id": "P",
            "pert_iname": target if j < n_target else "OTHER",
            "cell_id": "C",
            "pert_type": "trt_sh",
        })
    return _ArrayProvider(expr, pd.DataFrame(rows), symbols)


@pytest.fixture
def engine_factory(tmp_path, monkeypatch):
    """每个 engine 用独立的排名缓存文件，避免跨测试读到旧缓存。"""
    counter = {"n": 0}

    def make(provider):
        counter["n"] += 1
        monkeypatch.setattr(
            se, "_SHRNA_RANK_CACHE",
            str(tmp_path / f"rank_{counter['n']}.dat"),
        )
        monkeypatch.setattr(
            se, "_SHRNA_RANK_SHAPE",
            str(tmp_path / f"rank_{counter['n']}.txt"),
        )
        return SignatureEngine(provider)

    return make


# ---------------------------------------------------------------------------
# p 值平滑 / null 抽样
# ---------------------------------------------------------------------------

def test_p_values_never_zero_and_min_is_one_over_B_plus_1(engine_factory, monkeypatch):
    monkeypatch.setattr(se, "BOOTSTRAP_N", 7)
    monkeypatch.setattr(se, "FAST_MODE_TOP_N", 0)
    engine = engine_factory(_make_provider())
    sig = engine.compute_signature("G0")

    p = np.array([sig["p_values"][s] for s in sig["all_genes"]])
    assert np.all(p > 0)
    assert p.min() >= 1.0 / (sig["bootstrap_n"] + 1) - 1e-12
    # gene0 的观测 KS 严格大于任何 null KS → 取到最小 p
    assert sig["p_values"]["G0"] == pytest.approx(1.0 / (sig["bootstrap_n"] + 1))


class _RecordingRng:
    def __init__(self):
        self.calls = []

    def choice(self, pool, n, replace=False):
        pool = np.asarray(pool)
        self.calls.append((pool.copy(), n, replace))
        return pool[:n]


def test_bootstrap_excludes_target_columns_and_samples_without_replacement(engine_factory):
    engine = engine_factory(_make_provider())
    recorder = _RecordingRng()
    engine._rng = recorder

    n_pool = engine._shrna_rank_matrix.shape[1]
    exclude = np.array([0, 1, 2, 3])
    out = engine._bootstrap_null_ks(n_pool, 5, 3, exclude_cols=exclude)

    assert out.shape == (3, engine._n_genes)
    assert len(recorder.calls) == 3
    expected_pool = np.setdiff1d(np.arange(n_pool), exclude)
    for pool, n, replace in recorder.calls:
        assert n == 5
        assert replace is False
        assert np.array_equal(pool, expected_pool)
        # 无放回：一次抽样的下标互不重复
        assert len(set(pool[:n].tolist())) == n
        assert not set(pool.tolist()) & set(exclude.tolist())


# ---------------------------------------------------------------------------
# 快速模式 / n_sig / 每方向封顶
# ---------------------------------------------------------------------------

def _force_no_significant(engine, n_genes=20, n_boot=5):
    engine._bootstrap_null_ks = lambda *a, **k: np.full(
        (n_boot, n_genes), 1e9, dtype=np.float32
    )


def test_fast_mode_flag_reflects_actual_trigger(engine_factory, monkeypatch):
    provider = _make_provider()

    monkeypatch.setattr(se, "BOOTSTRAP_N", 5)
    monkeypatch.setattr(se, "FAST_MODE_TOP_N", 0)
    engine = engine_factory(provider)
    _force_no_significant(engine)
    sig = engine.compute_signature("G0")
    assert sig["up_genes"] == []
    assert sig["down_genes"] == []
    assert sig["n_sig"] == 0
    assert sig["fast_mode"] is False

    monkeypatch.setattr(se, "FAST_MODE_TOP_N", 3)
    engine2 = engine_factory(provider)
    _force_no_significant(engine2)
    sig2 = engine2.compute_signature("G0")
    assert sig2["fast_mode"] is True
    assert len(sig2["up_genes"]) + len(sig2["down_genes"]) == 3
    assert "params" in sig2
    assert sig2["params"]["FAST_MODE_TOP_N"] == config.FAST_MODE_TOP_N


def test_n_sig_counts_before_cap_and_cap_applies_per_direction(
    engine_factory, monkeypatch
):
    provider = _make_provider()
    monkeypatch.setattr(se, "BOOTSTRAP_N", 5)
    monkeypatch.setattr(se, "FAST_MODE_TOP_N", 0)
    monkeypatch.setattr(se, "FDR_THRESHOLD", 1.1)  # 让所有 KS 达标基因都通过
    engine = engine_factory(provider)
    # null 全 0 → p = 1/(B+1)，BH 后全部通过
    engine._bootstrap_null_ks = lambda *a, **k: np.zeros(
        (5, engine._n_genes), dtype=np.float32
    )

    monkeypatch.setattr(se, "MAX_GENES_PER_DIRECTION", 2)
    capped = engine.compute_signature("G0")
    assert capped["n_sig"] == 20  # 封顶前 10 up + 10 down
    assert len(capped["up_genes"]) == 2
    assert len(capped["down_genes"]) == 2
    # up 按 KS 降序，down 按 KS 升序
    assert capped["up_genes"] == ["G0", "G1"]
    assert capped["down_genes"] == ["G19", "G18"]

    monkeypatch.setattr(se, "MAX_GENES_PER_DIRECTION", 0)
    uncapped = engine.compute_signature("G0")
    assert uncapped["n_sig"] == 20
    assert len(uncapped["up_genes"]) == 10
    assert len(uncapped["down_genes"]) == 10


# ---------------------------------------------------------------------------
# XSUM / WTCS 方向
# ---------------------------------------------------------------------------

class _DrugProvider(_ArrayProvider):
    def __init__(self, expr, symbols, drug_names):
        sh_df = pd.DataFrame({
            "sig_id": ["SH0"], "pert_id": ["P"], "pert_iname": ["G0"],
            "cell_id": ["C"], "pert_type": ["trt_sh"],
        })
        super().__init__(expr, sh_df, symbols)
        self.drug_names = list(drug_names)

    def get_drug_samples(self):
        return pd.DataFrame({
            "sig_id": [f"D{i}" for i in range(len(self.drug_names))],
            "pert_id": ["P"] * len(self.drug_names),
            "pert_iname": self.drug_names,
            "cell_id": ["C"] * len(self.drug_names),
            "pert_type": ["trt_cp"] * len(self.drug_names),
        })

    def get_drug_expression_matrix(self, sig_ids):
        idx = [int(s[1:]) for s in sig_ids]
        return self.expr[:, idx].copy()

    def get_drug_name_map(self):
        return pd.Series(
            self.drug_names, index=[f"D{i}" for i in range(len(self.drug_names))]
        )


def test_xsum_high_score_means_reversal(tmp_path, monkeypatch):
    import drug_median_cache
    from drug_scorer import DrugScorer

    monkeypatch.setattr(
        drug_median_cache, "_DRUG_MEDIAN_PATH", str(tmp_path / "dm.npy")
    )
    monkeypatch.setattr(
        drug_median_cache, "_DRUG_NAMES_PATH", str(tmp_path / "dn.csv")
    )

    # 3 个基因 × 3 个药物；药物 D0 下调 up 基因、上调 down 基因 → 逆转
    expr = np.array([
        [-2.0, 2.0, 0.0],
        [2.0, -2.0, 0.0],
        [0.0, 0.0, 0.0],
    ], dtype=np.float32)
    provider = _DrugProvider(expr, ["A", "B", "C"], ["inhibitor", "mimic", "neutral"])
    scorer = DrugScorer(provider)

    sig = {"gene_name": "A", "up_genes": ["A"], "down_genes": ["B"]}
    xsum = scorer.score_drugs(sig, method="xsum")
    assert xsum["top_drugs"][0]["drug_name"] == "inhibitor"
    assert xsum["bottom_drugs"][0]["drug_name"] == "mimic"

    wtcs = scorer.score_drugs(sig, method="wtcs")
    assert wtcs["top_drugs"][0]["drug_name"] == "inhibitor"


# ---------------------------------------------------------------------------
# API：MIN_SH_SAMPLES 与返回字段
# ---------------------------------------------------------------------------

def _fixture_available():
    d = os.getenv("LMNA_FIXTURE_DIR")
    if not d:
        return False
    return all(
        os.path.exists(os.path.join(d, n))
        for n in (
            "lmna_fixture.npz",
            "lmna_fixture_sh.tsv",
            "lmna_fixture_cp.tsv",
            "lmna_fixture_meta.json",
        )
    )


@pytest.mark.skipif(not _fixture_available(), reason="未设置 LMNA_FIXTURE_DIR")
def test_api_status_and_compute_use_min_sh_samples(monkeypatch):
    from fastapi.testclient import TestClient
    import main as main_module

    client = TestClient(main_module.app)

    monkeypatch.setattr(config, "MIN_SH_SAMPLES", 3)
    body = client.get("/api/genes/CDK4/status").json()
    assert body["available"] == (body["n_shrna_samples"] >= 3)

    monkeypatch.setattr(config, "MIN_SH_SAMPLES", 1000)
    status = client.get("/api/genes/CDK4/status")
    assert status.status_code == 200
    assert status.json()["available"] is False

    resp = client.post("/api/genes/CDK4/compute", json={"method": "xsum"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "1000" in detail and str(status.json()["n_shrna_samples"]) in detail


@pytest.mark.skipif(not _fixture_available(), reason="未设置 LMNA_FIXTURE_DIR")
def test_signature_endpoint_returns_new_fields(monkeypatch):
    from cache_manager import CacheManager
    from fastapi.testclient import TestClient
    import main as main_module

    cache = CacheManager()
    cache.save_signature("L1FAKE", {
        "gene_name": "L1FAKE",
        "n_samples": 10,
        "n_sig": 7,
        "up_genes": ["A"],
        "down_genes": ["B"],
        "bootstrap_n": 1000,
        "fast_mode": True,
        "params": {"BOOTSTRAP_N": 1000},
    })
    client = TestClient(main_module.app)
    body = client.get("/api/genes/L1FAKE/signature").json()
    assert body["n_sig"] == 7
    assert body["fast_mode"] is True
    assert body["params"]["BOOTSTRAP_N"] == 1000
    cache.clear_gene("L1FAKE")


def test_task_result_contains_new_fields(monkeypatch):
    class _FakeCache:
        def get_signature(self, gene):
            return {
                "gene_name": gene,
                "n_samples": 12,
                "n_sig": 9,
                "up_genes": ["A"],
                "down_genes": ["B"],
                "fast_mode": True,
                "params": {"BOOTSTRAP_N": 1000},
            }

        def get_drug_scores(self, gene, method):
            return {
                "method": method,
                "top_drugs": [],
                "bottom_drugs": [],
            }

    monkeypatch.setattr(task_queue, "CacheManager", _FakeCache)
    monkeypatch.setattr(task_queue, "_build_provider", lambda _: None)

    result = task_queue._compute_task_worker("FAKE", "xsum", "l1testtask", "fixture")
    sig = result["signature"]
    assert sig["n_sig"] == 9
    assert sig["fast_mode"] is True
    assert sig["params"]["BOOTSTRAP_N"] == 1000

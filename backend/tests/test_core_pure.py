#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""不依赖夹具的纯函数 / 配置 / 工厂测试。"""

import os
import subprocess
import sys

import numpy as np
import pytest

import config
from data_provider import IDataProvider
from signature_engine import SignatureEngine, ks_uniform_batch
from l5_provider import L5Provider
from l3_provider import L3Provider
from provider_factory import create_provider


def test_cache_dir_is_configurable():
    assert config.CACHE_DIR == os.environ["LMNA_CACHE_DIR"]
    assert os.path.isdir(config.SIGNATURE_CACHE_DIR)
    assert os.path.isdir(config.DRUG_SCORE_CACHE_DIR)
    assert os.path.isdir(config.TASK_CACHE_DIR)


def test_test_env_defaults():
    assert config.DATA_PROVIDER == "fixture"
    assert config.BOOTSTRAP_N == 200
    assert config.FAST_MODE_TOP_N == 0
    assert os.environ["LMNA_TASK_INLINE"] == "1"


def test_default_provider_is_still_l5_without_env():
    """未设置 DATA_PROVIDER 时 create_provider 的默认值仍是 l5。"""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    env.pop("DATA_PROVIDER", None)
    env["PYTHONPATH"] = backend_dir
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import provider_factory as p; "
            "print(p.create_provider.__defaults__[0])",
        ],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "l5"


def test_create_provider_rejects_unknown_kind():
    with pytest.raises(ValueError):
        create_provider("not-a-provider")


def test_create_provider_fixture_without_dir_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("LMNA_FIXTURE_DIR", raising=False)
    with pytest.raises(FileNotFoundError):
        create_provider("fixture")


def test_abstract_interface_includes_all_shrna_samples():
    assert "get_all_shrna_samples" in IDataProvider.__abstractmethods__
    assert callable(getattr(L5Provider, "get_all_shrna_samples"))
    assert callable(getattr(L3Provider, "get_all_shrna_samples"))


def test_ks_uniform_batch_extremes():
    # ranks: 1 = 表达最高，978 = 表达最低
    # 统一符号约定：KS > 0 = 敲低后上调（rank 1），KS < 0 = 下调（rank 978）
    n = 50
    all_top = np.ones((1, n), dtype=np.int16)       # 全部排第 1
    all_bottom = np.full((1, n), 978, dtype=np.int16)  # 全部排第 978
    top_score = ks_uniform_batch(all_top, G=978)[0]
    bottom_score = ks_uniform_batch(all_bottom, G=978)[0]
    assert top_score > 0.9
    assert bottom_score < -0.9


def test_benjamini_hochberg_output_shape_and_range():
    # L1 已把 BH 修正为 scipy 等价实现，这里保留结构与取值范围检查。
    p = np.array([0.01, 0.04, 0.03, 0.5])
    q = SignatureEngine._benjamini_hochberg(p)
    assert q.shape == p.shape
    assert np.all((q >= 0) & (q <= 1))
    # 排序后的 q 值单调不减（按 p 排序后）
    assert np.all(np.diff(q[np.argsort(p)]) >= -1e-12)


class _FakeProvider(IDataProvider):
    """最小的内存 provider，用于验证排名缓存不再依赖私有属性。"""

    def __init__(self, n_sigs=20, n_genes=978):
        import pandas as pd

        self.n_genes = n_genes
        self.sig_ids = [f"S{i:03d}" for i in range(n_sigs)]
        self._df = pd.DataFrame({"sig_id": self.sig_ids})
        self.all_calls = 0

    def get_shrna_samples(self, gene_name):
        return self._df.copy()

    def get_all_shrna_samples(self):
        self.all_calls += 1
        return self._df.copy()

    def get_expression_matrix(self, sig_ids):
        idx = [self.sig_ids.index(s) for s in sig_ids]
        rng = np.random.default_rng(0)
        return rng.normal(size=(self.n_genes, len(idx))).astype(np.float32)

    def get_gene_symbols(self):
        return [f"G{i}" for i in range(self.n_genes)]

    def get_drug_samples(self):
        return self._df.copy()

    def get_drug_expression_matrix(self, sig_ids):
        return self.get_expression_matrix(sig_ids)

    def get_lm_gene_indices(self):
        return np.arange(self.n_genes)

    def get_vehicle_samples_for_plate(self, plate_id):
        raise NotImplementedError

    def list_available_genes(self):
        return []

    def get_drug_name_map(self):
        import pandas as pd

        return pd.Series(dtype=object)


def test_rank_cache_uses_public_interface(tmp_path, monkeypatch):
    import signature_engine as se

    cache_path = tmp_path / "rank.dat"
    shape_path = tmp_path / "rank_shape.txt"
    monkeypatch.setattr(se, "_SHRNA_RANK_CACHE", str(cache_path))
    monkeypatch.setattr(se, "_SHRNA_RANK_SHAPE", str(shape_path))

    provider = _FakeProvider(n_sigs=20)
    ranks = se._ensure_shrna_rank_cache(provider)

    assert provider.all_calls == 1
    assert ranks.shape == (978, 20)
    assert cache_path.exists()
    assert shape_path.exists()

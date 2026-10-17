#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在夹具上跑通 SignatureEngine（需要 LMNA_FIXTURE_DIR）。"""

import os

import numpy as np
import pytest

FIXTURE_DIR = os.getenv("LMNA_FIXTURE_DIR")
_REQUIRED = (
    "lmna_fixture.npz",
    "lmna_fixture_sh.tsv",
    "lmna_fixture_cp.tsv",
    "lmna_fixture_meta.json",
)
_AVAILABLE = bool(
    FIXTURE_DIR
    and os.path.isdir(FIXTURE_DIR)
    and all(os.path.exists(os.path.join(FIXTURE_DIR, n)) for n in _REQUIRED)
)

pytestmark = pytest.mark.skipif(
    not _AVAILABLE,
    reason="未设置 LMNA_FIXTURE_DIR 或夹具文件不完整",
)


def test_compute_signature_on_fixture():
    from fixture_provider import FixtureProvider
    from signature_engine import SignatureEngine

    provider = FixtureProvider()
    n_samples = len(provider.get_shrna_samples("CDK4"))
    engine = SignatureEngine(provider)
    sig = engine.compute_signature("CDK4")

    assert sig["gene_name"] == "CDK4"
    assert sig["n_samples"] == n_samples
    assert len(sig["all_ks"]) == 978
    assert sig["bootstrap_n"] == 200
    assert abs(sig["ks_scores"]["CDK4"]) > 0.2
    assert isinstance(sig["up_genes"], list)
    assert isinstance(sig["down_genes"], list)
    assert np.isfinite(sig["all_ks"]).all()

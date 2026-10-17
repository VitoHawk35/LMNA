#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FixtureProvider 接口测试（需要 LMNA_FIXTURE_DIR）。"""

import os

import numpy as np
import pytest

from fixture_provider import FixtureProvider


def _fixture_available() -> bool:
    fixture_dir = os.getenv("LMNA_FIXTURE_DIR")
    required = (
        "lmna_fixture.npz",
        "lmna_fixture_sh.tsv",
        "lmna_fixture_cp.tsv",
        "lmna_fixture_meta.json",
    )
    return bool(
        fixture_dir
        and os.path.isdir(fixture_dir)
        and all(os.path.exists(os.path.join(fixture_dir, n)) for n in required)
    )


pytestmark = pytest.mark.skipif(
    not _fixture_available(),
    reason="未设置 LMNA_FIXTURE_DIR 或夹具文件不完整",
)

TARGETS = ("CDK4", "TOP2A", "EGFR", "MTOR")


@pytest.fixture(scope="module")
def provider():
    return FixtureProvider()


def test_gene_symbols_and_matrix_shapes(provider):
    symbols = provider.get_gene_symbols()
    assert len(symbols) == 978
    assert len(set(symbols)) == 978
    sh_df = provider.get_all_shrna_samples()
    cp_df = provider.get_drug_samples()
    assert len(sh_df) > 3000
    assert len(cp_df) > 3000
    mat = provider.get_expression_matrix(sh_df["sig_id"].tolist()[:5])
    assert mat.shape == (978, 5)
    assert mat.dtype == np.float32
    dm = provider.get_drug_expression_matrix(cp_df["sig_id"].tolist()[:5])
    assert dm.shape == (978, 5)


def test_metadata_columns(provider):
    for df in (provider.get_all_shrna_samples(), provider.get_drug_samples()):
        for col in ("sig_id", "pert_id", "pert_iname", "cell_id", "pert_type"):
            assert col in df.columns


def test_four_targets_available(provider):
    genes = provider.list_available_genes()
    assert len(genes) >= 4
    for target in TARGETS:
        df = provider.get_shrna_samples(target)
        assert len(df) > 0, f"{target} 没有 shRNA 夹具样本"
        assert set(df["pert_type"]) == {"trt_sh"}


def test_expression_matrix_accepts_both_tables(provider):
    sh_sid = provider.get_all_shrna_samples()["sig_id"].iloc[0]
    cp_sid = provider.get_drug_samples()["sig_id"].iloc[0]
    mixed = provider.get_expression_matrix([sh_sid, cp_sid])
    assert mixed.shape == (978, 2)
    assert np.isfinite(mixed).all()


def test_unknown_sig_id_raises(provider):
    with pytest.raises(KeyError):
        provider.get_expression_matrix(["does-not-exist"])


def test_lm_indices_and_unsupported_vehicle(provider):
    idx = provider.get_lm_gene_indices()
    assert idx.dtype == np.int32
    assert np.array_equal(idx, np.arange(978))
    with pytest.raises(NotImplementedError):
        provider.get_vehicle_samples_for_plate("plate-1")


def test_drug_name_map(provider):
    mapping = provider.get_drug_name_map()
    cp_df = provider.get_drug_samples()
    assert len(mapping) == len(cp_df)
    assert mapping.index[0] == cp_df["sig_id"].iloc[0]


def test_inhibitor_metadata(provider):
    inhibitors = provider.get_target_inhibitors()
    for target in TARGETS:
        assert target in inhibitors
        assert len(inhibitors[target]) >= 1

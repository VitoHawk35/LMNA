#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L8 · 数据层列序对齐测试。

夹具 `tests/data/l8_col_order_slice.npz` 是从服务器/GSE92742 Level5 GCTX
抽取的**真实**真值切片（4 个 sig_id × 978 个 landmark 基因）：

  - 2 个 trt_cp（vorinostat，不同细胞系）
  - 2 个 trt_sh（EIF2AK3，两个 hairpin）
  - 列顺序 = 这 4 个 sig_id 在完整 GCTX COL 中的相对顺序

测试在同一份矩阵上分别使用两种 col_sig_ids.csv：

  - good：GCTX COL 顺序（修复后的正确文件）
  - bad ：按 sig_id 字典序排序（线上旧文件的错误语义）

注意：夹具的 row_gene_ids.csv 是**正确**的行序，目的是隔离本任务的列序 bug。
生产数据的 row_gene_ids.csv 另有行序错位（L8 已排查、任务要求只查不修），
见 deliveries/task-L8.md。
"""

import os

import numpy as np
import pandas as pd
import pytest

import l5_provider
from l5_provider import L5Provider

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "data", "l8_col_order_slice.npz")
pytestmark = pytest.mark.skipif(
    not os.path.exists(FIXTURE_PATH), reason="缺少 l8_col_order_slice.npz 夹具"
)


@pytest.fixture()
def slice_data():
    z = np.load(FIXTURE_PATH, allow_pickle=False)
    data = {
        "sig_ids": [str(x) for x in z["sig_ids"]],
        "pert_types": [str(x) for x in z["pert_types"]],
        "pert_inames": [str(x) for x in z["pert_inames"]],
        "pert_ids": [str(x) for x in z["pert_ids"]],
        "cell_ids": [str(x) for x in z["cell_ids"]],
        "gene_ids": [str(x) for x in z["gene_ids"]],
        "gene_symbols": [str(x) for x in z["gene_symbols"]],
        "matrix": np.asarray(z["matrix"], dtype=np.float32),  # (n_sigs, 978)
    }
    assert data["matrix"].shape == (len(data["sig_ids"]), len(data["gene_ids"]))
    return data


@pytest.fixture()
def data_dir(tmp_path, slice_data):
    """构造一个最小可用的 L5 数据目录（行序正确，只暴露列序问题）。"""
    d = tmp_path / "cmap_data"
    d.mkdir()

    # fast_matrix: (n_genes, n_sigs)，列序 = GCTX COL 顺序。
    # 生产文件是裸 memmap（无 .npy 头），这里用 tofile 保持一致。
    raw = np.ascontiguousarray(slice_data["matrix"].T, dtype=np.float32)
    raw.tofile(d / "fast_matrix.npy")

    pd.DataFrame({"gene_id": slice_data["gene_ids"]}).to_csv(
        d / "row_gene_ids.csv", index=False
    )
    pd.DataFrame({
        "pr_gene_id": slice_data["gene_ids"],
        "pr_gene_symbol": slice_data["gene_symbols"],
        "pr_is_lm": 1,
    }).to_csv(d / "gene_info.tsv", sep="\t", index=False)
    pd.DataFrame({
        "sig_id": slice_data["sig_ids"],
        "pert_id": slice_data["pert_ids"],
        "pert_iname": slice_data["pert_inames"],
        "cell_id": slice_data["cell_ids"],
        "pert_type": slice_data["pert_types"],
        "distil_id": [""] * len(slice_data["sig_ids"]),
    }).to_csv(d / "sig_info.tsv", sep="\t", index=False)

    # good = GCTX COL 顺序；bad = 旧文件的字典序
    pd.DataFrame({"sig_id": slice_data["sig_ids"]}).to_csv(
        d / "col_sig_ids.good.csv", index=False
    )
    pd.DataFrame({"sig_id": sorted(slice_data["sig_ids"])}).to_csv(
        d / "col_sig_ids.bad.csv", index=False
    )

    # D1：默认 fingerprint 模式需要 integrity.json；按"good"花名册生成，
    # bad 花名册会被指纹比对拒绝（这正是防线1 的验收语义）。
    import lincs_integrity

    fp = lincs_integrity.build_fingerprint(
        matrix_path=str(d / "fast_matrix.npy"),
        row_csv_path=str(d / "row_gene_ids.csv"),
        col_csv_path=str(d / "col_sig_ids.good.csv"),
    )
    lincs_integrity.write_fingerprint(fp, str(d / "integrity.json"))
    return d


def _make_provider(monkeypatch, data_dir, col_filename, check_order=True):
    monkeypatch.setattr(l5_provider, "MATRIX_PATH", str(data_dir / "fast_matrix.npy"))
    monkeypatch.setattr(l5_provider, "COL_NAMES_PATH", str(data_dir / col_filename))
    monkeypatch.setattr(l5_provider, "ROW_NAMES_PATH", str(data_dir / "row_gene_ids.csv"))
    monkeypatch.setattr(l5_provider, "GENE_INFO_PATH", str(data_dir / "gene_info.tsv"))
    monkeypatch.setattr(l5_provider, "SIG_INFO_PATH", str(data_dir / "sig_info.tsv"))
    monkeypatch.setattr(l5_provider, "N_GENES", len(
        pd.read_csv(data_dir / "row_gene_ids.csv")
    ))
    monkeypatch.setattr(l5_provider, "N_SIGS", len(
        pd.read_csv(data_dir / col_filename)
    ))
    monkeypatch.setattr(l5_provider, "CHECK_COL_ORDER", check_order)
    L5Provider._instance = None
    try:
        return L5Provider()
    finally:
        # 避免后续测试复用带旧 monkeypatch 路径的单例
        L5Provider._instance = None


def test_fixture_covers_cp_and_sh(slice_data):
    types = set(slice_data["pert_types"])
    assert "trt_cp" in types
    assert "trt_sh" in types
    assert len(slice_data["sig_ids"]) >= 3


def test_fixed_col_names_match_gctx_truth(monkeypatch, data_dir, slice_data):
    """验收 1：修复后 3+ 个 sig_id 的 978 维向量与 GCTX 真值逐元素一致。"""
    provider = _make_provider(monkeypatch, data_dir, "col_sig_ids.good.csv")

    sig_ids = slice_data["sig_ids"][:3]
    got = provider.get_expression_matrix(sig_ids)
    truth = slice_data["matrix"][:3].T

    assert got.shape == (978, 3)
    max_diff = float(np.max(np.abs(got - truth)))
    assert np.allclose(got, truth, atol=0, rtol=0) or max_diff < 1e-5
    assert max_diff < 1e-5, f"max abs diff = {max_diff}"


def test_all_four_sigs_match_gctx_truth(monkeypatch, data_dir, slice_data):
    provider = _make_provider(monkeypatch, data_dir, "col_sig_ids.good.csv")
    got = provider.get_expression_matrix(slice_data["sig_ids"])
    assert got.shape == (978, len(slice_data["sig_ids"]))
    assert float(np.max(np.abs(got - slice_data["matrix"].T))) < 1e-5


def test_sorted_col_names_are_rejected(monkeypatch, data_dir):
    """验收 2a：旧排序文件在修复后会被 fail-fast 拒绝，而不是静默读错。"""
    with pytest.raises(RuntimeError, match="col_sig_ids.csv"):
        _make_provider(monkeypatch, data_dir, "col_sig_ids.bad.csv", check_order=True)


def test_sorted_col_names_read_wrong_columns(monkeypatch, data_dir, slice_data):
    """验收 2b：关闭哨兵后复现旧行为——排序映射确实读到错误的签名。"""
    # D1：本用例故意复现"花名册错位"的旧行为，需同时关闭防线1（仅供测试）。
    monkeypatch.setenv("LINCS_INTEGRITY_MODE", "off")
    provider = _make_provider(
        monkeypatch, data_dir, "col_sig_ids.bad.csv", check_order=False
    )
    got = provider.get_expression_matrix(slice_data["sig_ids"])
    truth = slice_data["matrix"].T
    max_diff = float(np.max(np.abs(got - truth)))
    assert max_diff > 1e-3, "旧排序映射应当与 GCTX 真值明显不一致"
    # 两个 vorinostat cp 的列被互换了（排序序与 GCTX COL 序相反）
    assert np.array_equal(got[:, 0], truth[:, 1])
    assert np.array_equal(got[:, 1], truth[:, 0])


def test_drug_median_rebuilt_from_fixed_provider(monkeypatch, data_dir, slice_data,
                                                tmp_path):
    """验收 3：修复后的 provider 重建药物中位数，抽查 1 个药物与真值吻合。"""
    import drug_median_cache as dmc

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(dmc, "_DRUG_MEDIAN_PATH", str(cache_dir / "_drug_median_matrix.npy"))
    monkeypatch.setattr(dmc, "_DRUG_NAMES_PATH", str(cache_dir / "_drug_names.csv"))

    provider = _make_provider(monkeypatch, data_dir, "col_sig_ids.good.csv")
    matrix, names = dmc.get_drug_median_matrix(provider)

    assert names == ["vorinostat"]
    cp_idx = [i for i, t in enumerate(slice_data["pert_types"]) if t == "trt_cp"]
    truth = np.median(slice_data["matrix"][cp_idx, :], axis=0)
    got = np.asarray(matrix[:, names.index("vorinostat")])

    r = float(np.corrcoef(got, truth)[0, 1])
    assert r > 0.99, f"corr = {r}"
    assert float(np.max(np.abs(got - truth))) < 1e-5

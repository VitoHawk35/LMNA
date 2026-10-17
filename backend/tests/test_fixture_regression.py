#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""夹具回归：KS 符号、签名集合、XSUM 方向（需要 LMNA_FIXTURE_DIR）。

期望的 up/down 集合从夹具目录下的 lmna_fixture_expected.json 读取。
L0 重建夹具时未保存该文件，L1 用修正后的算法、固定种子与
BOOTSTRAP_N=1000 / MAX_GENES_PER_DIRECTION=50 生成并随夹具保存；
该 Jaccard 检查用于锁定可复现性，参考 KS 与抑制剂百分位是独立校验。
"""

import json
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

TARGETS = ("CDK4", "TOP2A", "EGFR")
REFERENCE_KS = {"CDK4": -0.746, "TOP2A": -0.837, "EGFR": -0.460}
EXPECTED_PATH = os.path.join(FIXTURE_DIR or "", "lmna_fixture_expected.json")
TABLE_S1_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "table_s1.tsv")


@pytest.fixture(scope="module")
def fixed_params():
    """按验收条件固定 B=1000、快速模式关闭、每方向封顶 50。"""
    import signature_engine as se

    saved = (
        se.BOOTSTRAP_N,
        se.FAST_MODE_TOP_N,
        se.MAX_GENES_PER_DIRECTION,
    )
    se.BOOTSTRAP_N = 1000
    se.FAST_MODE_TOP_N = 0
    se.MAX_GENES_PER_DIRECTION = 50
    yield
    (
        se.BOOTSTRAP_N,
        se.FAST_MODE_TOP_N,
        se.MAX_GENES_PER_DIRECTION,
    ) = saved


@pytest.fixture(scope="module")
def provider():
    from fixture_provider import FixtureProvider

    return FixtureProvider()


@pytest.fixture(scope="module")
def signatures(provider, fixed_params):
    from signature_engine import SignatureEngine

    result = {}
    for gene in TARGETS:
        # 每个靶点独立 engine，随机种子固定为 RANDOM_SEED
        result[gene] = SignatureEngine(provider).compute_signature(gene)
    return result


@pytest.mark.parametrize("gene", TARGETS)
def test_target_gene_is_downregulated(signatures, gene):
    sig = signatures[gene]
    ks = sig["ks_scores"][gene]

    assert ks < 0, f"{gene} 敲低后应下调，KS 应为负，实际 {ks}"
    assert gene in sig["down_genes"], f"{gene} 应出现在 down_genes"
    assert gene not in sig["up_genes"]
    assert abs(ks) > 0.2
    # 夹具样本覆盖与论文参考集略有差异（EGFR 尤甚），允许 0.12 偏差
    assert abs(ks - REFERENCE_KS[gene]) <= 0.12


@pytest.mark.parametrize("gene", TARGETS)
def test_signature_jaccard_against_expected(signatures, gene):
    if not os.path.exists(EXPECTED_PATH):
        pytest.skip("缺少 lmna_fixture_expected.json（L0 未保存期望值）")

    with open(EXPECTED_PATH, "r", encoding="utf-8") as f:
        expected = json.load(f)[gene]

    for direction in ("up_genes", "down_genes"):
        got = set(signatures[gene][direction])
        want = set(expected[direction])
        union = got | want
        jaccard = len(got & want) / len(union) if union else 1.0
        assert jaccard >= 0.8, f"{gene} {direction} Jaccard={jaccard:.3f} < 0.8"


@pytest.mark.parametrize("gene", TARGETS)
def test_xsum_known_inhibitor_at_simulation_end(signatures, provider, gene):
    from drug_scorer import DrugScorer

    sig = signatures[gene]
    scorer = DrugScorer(provider)
    result = scorer.score_drugs(sig, method="xsum")

    scores = {row["drug_name"]: float(row["score"]) for row in result["all_scores"]}
    inhibitors = [
        name for name in provider.meta["inhibitors"][gene] if name in scores
    ]
    assert inhibitors, f"{gene} 的已知抑制剂都不在夹具药物表中"

    # score 越低越靠"模拟/加重"端；取抑制剂中最低分的那个
    lowest = min(inhibitors, key=lambda name: scores[name])
    values = np.array(list(scores.values()), dtype=float)
    percentile = float(np.mean(values >= scores[lowest]))
    assert percentile >= 0.95, (
        f"{gene} 抑制剂 {lowest} 位于 bottom 的百分位 {percentile:.3f} < 0.95"
    )


@pytest.mark.skipif(
    not os.path.exists(TABLE_S1_PATH),
    reason="D3: 未提供论文 Table S1（backend/tests/fixtures/table_s1.tsv）",
)
def test_paper_table_s1_jaccard(signatures):
    """D3 参考项：新签名与论文 Table S1 的 Jaccard ≥ 0.6（只作参考）。"""
    import pandas as pd

    df = pd.read_csv(TABLE_S1_PATH, sep="\t")
    required = {"target", "direction", "gene"}
    if not required.issubset(df.columns):
        pytest.skip("Table S1 格式无法识别（需要 target/direction/gene 长表）")

    for gene in TARGETS:
        sub = df[df["target"].astype(str).str.upper() == gene]
        for direction in ("up_genes", "down_genes"):
            key = direction.replace("_genes", "")
            want = set(
                sub[sub["direction"].astype(str).str.lower() == key]["gene"]
                .astype(str).str.upper()
            )
            got = set(signatures[gene][direction])
            union = got | want
            jaccard = len(got & want) / len(union) if union else 1.0
            assert jaccard >= 0.6, f"{gene} {direction} Jaccard={jaccard:.3f} < 0.6"

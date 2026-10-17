#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L3 基因适用性判档测试。

覆盖：
- 红/黄/绿边界（n_sig、loho_jaccard_min、fast_mode、hairpin < 2）；
- 注释表缺失 → "未知"、注释各列对判档的影响；
- 夹具四靶点判档与 LOHO 参考值；
- 1 个 hairpin 的基因 → /suitability data_gate_ok False、/compute 422；
- 红档 /drugs 空列表 + include_red=true 恢复正常；
- mode=gof 时 CDK4 已知抑制剂进入 top 5%。
"""

import json
import os

import numpy as np
import pytest

import config
import suitability
from suitability import grade, load_annotation, loho_jaccard_min, precheck

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

requires_fixture = pytest.mark.skipif(
    not _AVAILABLE,
    reason="未设置 LMNA_FIXTURE_DIR 或夹具文件不完整",
)

# 报告 4.4b 参考 LOHO（容差 ±0.05）。
# EGFR 夹具只取前 150 个 trt_sh（15 个 hairpin），论文参考集为 19 个 hairpin，
# L1 已记录该样本覆盖差异（KS −0.528 vs −0.460）；因此 EGFR 容差放宽到 0.10，
# 档位仍为绿档。详见 deliveries/task-L3.md。
REFERENCE_LOHO = {
    "CDK4": (0.587, 0.05),
    "EGFR": (0.532, 0.10),
    "MTOR": (0.549, 0.05),
    "TOP2A": (0.290, 0.05),
}


# ---------------------------------------------------------------------------
# 纯函数：红/黄/绿边界
# ---------------------------------------------------------------------------

def _make_pre(data_gate_ok=True):
    return {
        "gene_name": "G",
        "n_samples": 10,
        "n_hairpins": 3 if data_gate_ok else 1,
        "n_cells": 4,
        "cell_lines": ["A375", "MCF7", "PC3", "VCAP"],
        "data_gate_ok": data_gate_ok,
        "reasons": ["测试"],
    }


def _make_sig(n_sig=10, loho=0.6, fast=False):
    up = ["U1", "U2", "U3"]
    down = ["D1", "D2", "D3"]
    return {
        "gene_name": "G",
        "n_sig": n_sig,
        "up_genes": up,
        "down_genes": down,
        "fast_mode": fast,
        "ks_scores": {"G": -0.5, "U1": 0.4, "D1": -0.4},
        "target_median_z": -1.25,
        "loho_jaccard_min": loho,
        "loho_detail": {
            "k": 10,
            "n_hairpins": 3,
            "n_hairpins_used": 3,
            "n_hairpins_skipped": 0,
        },
    }


@pytest.mark.parametrize(
    "n_sig,loho,fast,data_gate_ok,expected",
    [
        (5, 0.50, False, True, "green"),   # 绿档下边界
        (20, 0.50, False, True, "green"),  # 绿档
        (4, 0.90, False, True, "red"),     # n_sig < 5
        (5, 0.499, False, True, "red"),    # 未达绿档且 n_sig < 20，不满足黄档
        (19, 0.40, False, True, "red"),    # 黄档要求 n_sig >= 20
        (20, 0.30, False, True, "yellow"), # 黄档下边界
        (20, 0.499, False, True, "yellow"),# 黄档上边界（不含 0.5）
        (20, 0.299, False, True, "red"),   # Jaccard < 0.3
        (10, None, False, True, "red"),    # 无法计算 LOHO
        (10, 0.60, True, True, "red"),     # fast_mode 一票否决
        (10, 0.60, False, False, "red"),   # 数据门槛未过
    ],
)
def test_grade_boundaries(n_sig, loho, fast, data_gate_ok, expected):
    result = grade(
        _make_sig(n_sig=n_sig, loho=loho, fast=fast),
        _make_pre(data_gate_ok=data_gate_ok),
    )
    assert result["grade"] == expected
    assert result["n_sig"] == n_sig
    assert result["loho_jaccard_min"] == loho
    assert result["reasons"]


def test_grade_reference_is_display_only():
    result = grade(_make_sig(n_sig=10, loho=0.6), _make_pre())
    ref = result["reference"]
    assert ref["n_cells"] == 4
    assert ref["target_is_landmark"] is True
    assert ref["target_ks"] == -0.5
    assert ref["target_median_z"] == -1.25
    assert ref["loho_hairpins_used"] == 3


def test_grade_missing_annotation_is_unknown_and_does_not_change_tier():
    result = grade(
        _make_sig(n_sig=10, loho=0.6),
        _make_pre(),
        annotation=None,
    )
    assert result["grade"] == "green"
    assert result["annotation_used"] is False
    assert any("未知" in reason for reason in result["reasons"])


def test_annotation_not_expressed_forces_red():
    result = grade(
        _make_sig(n_sig=30, loho=0.8),
        _make_pre(),
        annotation={
            "gene": "G",
            "expressed_in_l1000_cells": False,
            "tissue_specific": False,
            "receptor_or_channel": False,
        },
    )
    assert result["grade"] == "red"
    assert any("不表达" in reason for reason in result["reasons"])


def test_annotation_tissue_specific_receptor_forces_red():
    result = grade(
        _make_sig(n_sig=30, loho=0.8),
        _make_pre(),
        annotation={
            "gene": "G",
            "expressed_in_l1000_cells": True,
            "tissue_specific": True,
            "receptor_or_channel": True,
        },
    )
    assert result["grade"] == "red"
    assert any("受体" in reason for reason in result["reasons"])


def test_annotation_tissue_specific_downgrades_green_to_yellow():
    result = grade(
        _make_sig(n_sig=30, loho=0.8),
        _make_pre(),
        annotation={
            "gene": "G",
            "expressed_in_l1000_cells": True,
            "tissue_specific": True,
            "receptor_or_channel": False,
        },
    )
    assert result["grade"] == "yellow"
    assert any("组织专有" in reason for reason in result["reasons"])


def test_broadly_expressed_receptor_is_not_automatically_red():
    # EGFR 这类广泛表达的受体不应仅因 receptor_or_channel=True 判红
    result = grade(
        _make_sig(n_sig=30, loho=0.8),
        _make_pre(),
        annotation={
            "gene": "G",
            "expressed_in_l1000_cells": True,
            "tissue_specific": False,
            "receptor_or_channel": True,
        },
    )
    assert result["grade"] == "green"


def test_load_annotation_parses_booleans_and_missing_gene(tmp_path):
    path = tmp_path / "gene_annotations.tsv"
    path.write_text(
        "gene\texpressed_in_l1000_cells\ttissue_specific\treceptor_or_channel\n"
        "CDK4\tTRUE\tFALSE\tFALSE\n"
        "SCN5A\tFALSE\tTRUE\tTRUE\n"
        "UNKNOWN1\t\t\t\n",
        encoding="utf-8",
    )

    ann, reason = load_annotation("cdk4", path=str(path))
    assert reason is None
    assert ann["expressed_in_l1000_cells"] is True
    assert ann["tissue_specific"] is False
    assert ann["receptor_or_channel"] is False

    ann2, _ = load_annotation("SCN5A", path=str(path))
    assert ann2["expressed_in_l1000_cells"] is False
    assert ann2["tissue_specific"] is True
    assert ann2["receptor_or_channel"] is True

    ann3, _ = load_annotation("UNKNOWN1", path=str(path))
    assert ann3["expressed_in_l1000_cells"] is None
    assert ann3["tissue_specific"] is None

    ann4, reason4 = load_annotation("NOT_IN_TABLE", path=str(path))
    assert ann4 is None
    assert "没有" in reason4 and "未知" in reason4

    ann5, reason5 = load_annotation("CDK4", path=str(tmp_path / "missing.tsv"))
    assert ann5 is None
    assert "未提供" in reason5


# ---------------------------------------------------------------------------
# LOHO 纯函数
# ---------------------------------------------------------------------------

def test_loho_skips_hairpins_with_too_few_remaining():
    # 2 条 hairpin × 2 个样本；去掉任意一条后只剩 2 个（< 3）→ 全部跳过
    ranks = np.tile(np.arange(1, 21, dtype=np.int16)[:, None], (1, 4))
    loho, detail = loho_jaccard_min(
        ranks,
        ["H1", "H1", "H2", "H2"],
        full_top_indices=np.arange(10),
        G=20,
        k=10,
    )
    assert loho is None
    assert detail["n_hairpins"] == 2
    assert detail["n_hairpins_used"] == 0
    assert detail["n_hairpins_skipped"] == 2


def test_loho_identical_recompute_gives_one():
    # 每条样本的秩完全相同 → 去掉任意 hairpin 后 KS 排序不变 → Jaccard = 1
    from signature_engine import ks_uniform_batch

    base = np.arange(1, 21, dtype=np.int16)
    ranks = np.tile(base[:, None], (1, 6))
    full_top = np.argsort(-np.abs(ks_uniform_batch(ranks, 20)))[:10]
    loho, detail = loho_jaccard_min(
        ranks,
        ["H1", "H1", "H2", "H2", "H3", "H3"],
        full_top_indices=full_top,
        G=20,
        k=10,
    )
    assert loho == pytest.approx(1.0)
    assert detail["n_hairpins_used"] == 3
    assert detail["k"] == 10


def test_loho_uses_k_from_capped_gene_counts():
    # k = max(10, len(up)+len(down))；detail 记录实际使用的 k
    base = np.arange(1, 21, dtype=np.int16)
    ranks = np.tile(base[:, None], (1, 4))
    _, detail = loho_jaccard_min(
        ranks,
        ["H1", "H1", "H2", "H2"],
        full_top_indices=np.arange(15),
        G=20,
        k=15,
    )
    assert detail["k"] == 15


# ---------------------------------------------------------------------------
# 夹具：precheck / 判档 / LOHO 参考值
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def provider():
    from fixture_provider import FixtureProvider

    return FixtureProvider()


@pytest.fixture(scope="module")
def signatures(provider):
    from signature_engine import SignatureEngine

    return {
        gene: SignatureEngine(provider).compute_signature(gene)
        for gene in ("CDK4", "EGFR", "MTOR", "TOP2A")
    }


@requires_fixture
def test_precheck_fixture_cdk4_and_single_hairpin(provider):
    ok = precheck(provider, "CDK4")
    assert ok["n_samples"] == 86
    assert ok["n_hairpins"] == 7
    assert ok["n_cells"] == 11
    assert ok["data_gate_ok"] is True

    # ABHD4：3 个样本但只有 1 个独立 hairpin
    bad = precheck(provider, "ABHD4")
    assert bad["n_samples"] == 3
    assert bad["n_hairpins"] == 1
    assert bad["data_gate_ok"] is False
    assert any("hairpin" in reason for reason in bad["reasons"])


@requires_fixture
@pytest.mark.parametrize("gene", ["CDK4", "EGFR", "MTOR", "TOP2A"])
def test_loho_reference_values(signatures, gene):
    reference, tolerance = REFERENCE_LOHO[gene]
    got = signatures[gene]["loho_jaccard_min"]
    assert got is not None
    assert abs(got - reference) <= tolerance, (
        f"{gene} LOHO={got:.3f} 与参考 {reference:.3f} 相差超过 {tolerance}"
    )


@requires_fixture
@pytest.mark.parametrize(
    "gene,expected",
    [("CDK4", "green"), ("EGFR", "green"), ("MTOR", "green"), ("TOP2A", "red")],
)
def test_fixture_grades(signatures, gene, expected):
    sig = signatures[gene]
    qc = sig["qc"]
    assert qc["grade"] == expected
    assert qc["n_sig"] == sig["n_sig"]
    assert qc["loho_jaccard_min"] == sig["loho_jaccard_min"]
    assert qc["rule_version"] == suitability.RULE_VERSION
    # 夹具目录没有 gene_annotations.tsv → 第一层未知，不影响档位
    assert qc["annotation_used"] is False
    assert any("未知" in reason for reason in qc["reasons"])


@requires_fixture
def test_loho_detail_uses_capped_counts(signatures):
    for gene in ("CDK4", "EGFR", "MTOR", "TOP2A"):
        sig = signatures[gene]
        expected_k = max(
            10, len(sig["up_genes"]) + len(sig["down_genes"])
        )
        assert sig["loho_detail"]["k"] == expected_k
        assert sig["loho_detail"]["n_hairpins_used"] == sig["n_hairpins"]
        assert sig["loho_detail"]["n_hairpins_skipped"] == 0


@requires_fixture
def test_signature_contains_suitability_fields(signatures):
    sig = signatures["CDK4"]
    for key in (
        "qc",
        "n_hairpins",
        "n_cells",
        "loho_jaccard_min",
        "loho_detail",
        "target_median_z",
    ):
        assert key in sig


# ---------------------------------------------------------------------------
# API：/suitability、/compute 门槛、/drugs 红档与 gof
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import main as main_module

    return TestClient(main_module.app)


@requires_fixture
def test_suitability_endpoint_single_hairpin(client):
    body = client.get("/api/genes/ABHD4/suitability").json()
    assert body["gene_name"] == "ABHD4"
    assert body["precheck"]["data_gate_ok"] is False
    assert body["precheck"]["n_hairpins"] == 1
    assert body["qc"] is None
    assert body["grade"] is None


@requires_fixture
def test_compute_rejects_single_hairpin(client):
    resp = client.post("/api/genes/ABHD4/compute", json={"method": "xsum"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "hairpin" in detail
    assert "脱靶" in detail


@requires_fixture
def test_red_gene_drugs_are_empty_and_include_red_restores(
    client, provider, signatures
):
    from cache_manager import CacheManager
    from drug_scorer import DrugScorer

    cache = CacheManager()
    sig = signatures["TOP2A"]
    assert sig["qc"]["grade"] == "red"
    cache.save_signature("TOP2A", sig)
    drug_data = DrugScorer(provider).score_drugs(sig, method="xsum")
    cache.save_drug_scores("TOP2A", "xsum", drug_data)

    try:
        # /suitability 附上缓存签名里的 qc
        suitability_body = client.get("/api/genes/TOP2A/suitability").json()
        assert suitability_body["qc"]["grade"] == "red"
        assert suitability_body["grade"] == "red"
        assert suitability_body["cached_signature"] is True

        resp = client.get("/api/genes/TOP2A/drugs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["qc"]["grade"] == "red"
        assert body["top_drugs"] == []
        assert body["bottom_drugs"] == []
        assert body["red_suppressed"] is True

        resp2 = client.get(
            "/api/genes/TOP2A/drugs", params={"include_red": True}
        )
        body2 = resp2.json()
        assert len(body2["top_drugs"]) > 0
        assert len(body2["bottom_drugs"]) > 0
        assert body2["red_suppressed"] is False
    finally:
        cache.clear_gene("TOP2A")


@requires_fixture
def test_gof_mode_puts_cdk4_inhibitors_in_top_5_percent(
    client, provider, signatures
):
    from cache_manager import CacheManager
    from drug_scorer import DrugScorer

    sig = signatures["CDK4"]
    scorer = DrugScorer(provider)
    result = scorer.score_drugs(
        sig, method="xsum", mode="gof", top_k=200, bottom_k=200
    )

    # gof：top 列表按 score 升序（模拟药）
    top_scores = [row["score"] for row in result["top_drugs"]]
    assert top_scores == sorted(top_scores)

    scores = {row["drug_name"]: float(row["score"]) for row in result["all_scores"]}
    all_values = np.array(list(scores.values()), dtype=float)
    cutoff = float(np.quantile(all_values, 0.05))  # 最低 5% 的分数上界
    inhibitors = [
        name for name in provider.meta["inhibitors"]["CDK4"] if name in scores
    ]
    assert inhibitors
    assert any(scores[name] <= cutoff for name in inhibitors), (
        "CDK4 已知抑制剂应进入 gof 模式的 top 5%（最低分端）"
    )
    assert "palbociclib" in scores
    assert scores["palbociclib"] <= cutoff

    cache = CacheManager()
    cache.save_signature("CDK4", sig)
    gof_data = scorer.score_drugs(sig, method="xsum", mode="gof")
    cache.save_drug_scores("CDK4", "xsum", gof_data, mode="gof")
    try:
        body = client.get(
            "/api/genes/CDK4/drugs",
            params={"mode": "gof", "top_n": 200, "bottom_n": 10},
        ).json()
        assert body["mode"] == "gof"
        names = [row["drug_name"] for row in body["top_drugs"]]
        assert "palbociclib" in names
        assert body["qc"]["grade"] == "green"
    finally:
        cache.clear_gene("CDK4")


# ---------------------------------------------------------------------------
# 任务结果：红档同样屏蔽药物列表
# ---------------------------------------------------------------------------

def test_task_result_suppresses_red_drugs(monkeypatch):
    import task_queue

    class _RedCache:
        def get_signature(self, gene):
            return {
                "gene_name": gene,
                "n_samples": 10,
                "n_sig": 3,
                "up_genes": [],
                "down_genes": [],
                "fast_mode": False,
                "params": {},
                "qc": {"grade": "red", "reasons": ["测试"]},
                "n_hairpins": 2,
                "n_cells": 3,
            }

        def get_drug_scores(self, gene, method, mode="lof"):
            return {
                "method": method,
                "mode": mode,
                "top_drugs": [{"drug_name": "X", "score": 1.0}],
                "bottom_drugs": [{"drug_name": "Y", "score": -1.0}],
            }

    monkeypatch.setattr(task_queue, "CacheManager", lambda: _RedCache())
    monkeypatch.setattr(task_queue, "_build_provider", lambda _: None)

    result = task_queue._compute_task_worker(
        "FAKE", "xsum", "l3-red-task", "fixture", score_mode="gof"
    )
    assert result["signature"]["qc"]["grade"] == "red"
    assert result["drug_results"]["red_suppressed"] is True
    assert result["drug_results"]["top_drugs"] == []
    assert result["drug_results"]["bottom_drugs"] == []
    assert result["drug_results"]["mode"] == "gof"

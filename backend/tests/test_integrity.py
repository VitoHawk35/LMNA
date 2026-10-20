#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""D1 · 数据完整性防线测试。

防线1（启动逐 ID / 指纹比对）：
- 5 种花名册状态：正确、字母排序、随机打乱、10% 位置互换、只错 1 位；
  行、列各测一遍，gctx 与 fingerprint 两种模式各跑一遍（后 4 种必须拒绝启动）；
- 指纹模式下矩阵被换成同形状的另一个文件 → 拒绝启动；
- 缺 integrity.json → 拒绝启动并给出修复命令；
- LINCS_INTEGRITY_MODE=off → 放行但打 WARNING；
- 文件末尾多空行 → 按约定容忍并打 WARNING（不静默）。

防线2（生物学自检 + 判档规则 4.5）：
- 哨兵自检：全通过 ok；2/3 以上不通过 suspect；无可用哨兵 unknown；
- landmark 靶基因自身 KS > 0 → 最高黄档（理由含"敲低可能未生效或数据有误"）；
- 夹具上 CDK4 结果不变（234 / 0.587 / 绿），伪签名（自身 KS 改正值）判黄档；
- /api/health 暴露 integrity / integrity_mode 字段。
"""

import copy
import json
import os

import numpy as np
import pandas as pd
import pytest

import lincs_integrity
from lincs_integrity import (
    build_fingerprint,
    check_startup,
    write_fingerprint,
)

h5py = pytest.importorskip("h5py", reason="gctx 模式测试需要 h5py")

N_GENES = 40
N_SIGS = 60

FIXTURE_DIR = os.getenv("LMNA_FIXTURE_DIR")
_FIXTURE_FILES = (
    "lmna_fixture.npz",
    "lmna_fixture_sh.tsv",
    "lmna_fixture_cp.tsv",
    "lmna_fixture_meta.json",
)
_FIXTURE_OK = bool(
    FIXTURE_DIR
    and os.path.isdir(FIXTURE_DIR)
    and all(os.path.exists(os.path.join(FIXTURE_DIR, n)) for n in _FIXTURE_FILES)
)
requires_fixture = pytest.mark.skipif(
    not _FIXTURE_OK, reason="未设置 LMNA_FIXTURE_DIR 或夹具文件不完整"
)


# ---------------------------------------------------------------------------
#  tiny L5 数据目录（行/列 ID 均故意非字典序，确保"排序"是真正的破坏）
# ---------------------------------------------------------------------------

def _good_ids():
    rng = np.random.RandomState(2026)
    row_ids = [str(x) for x in rng.choice(range(10000, 99999), N_GENES, replace=False)]
    col_ids = [
        "SIG%s%04d" % ("".join(rng.choice(list("ABCDEFGH"), 3)), i)
        for i in rng.choice(range(1000, 9999), N_SIGS, replace=False)
    ]
    return row_ids, col_ids


def _write_matrix(path, seed):
    rng = np.random.RandomState(seed)
    mat = rng.standard_normal((N_GENES, N_SIGS)).astype(np.float32)
    np.ascontiguousarray(mat).tofile(str(path))
    return mat


def _write_gctx(path, row_ids, col_ids):
    with h5py.File(str(path), "w") as f:
        meta = f.create_group("0/META")
        meta.create_dataset(
            "ROW/id", data=np.array([int(x) for x in row_ids], dtype=np.int64)
        )
        meta.create_dataset(
            "COL/id", data=np.array([x.encode() for x in col_ids], dtype="S32")
        )


def _make_data_dir(tmp_path, matrix_seed=42, with_fingerprint=True, with_gctx=True):
    d = tmp_path / "cmap_data"
    d.mkdir()
    row_ids, col_ids = _good_ids()
    _write_matrix(d / "fast_matrix.npy", matrix_seed)
    pd.DataFrame({"gene_id": row_ids}).to_csv(d / "row_gene_ids.csv", index=False)
    pd.DataFrame({"sig_id": col_ids}).to_csv(d / "col_sig_ids.csv", index=False)
    if with_gctx:
        _write_gctx(d / "tiny.gctx", row_ids, col_ids)
    if with_fingerprint:
        fp = build_fingerprint(
            matrix_path=str(d / "fast_matrix.npy"),
            row_csv_path=str(d / "row_gene_ids.csv"),
            col_csv_path=str(d / "col_sig_ids.csv"),
        )
        write_fingerprint(fp, str(d / "integrity.json"))
    return d, row_ids, col_ids


def _tamper(ids, kind):
    ids = list(ids)
    if kind == "correct":
        return ids
    if kind == "sorted":
        out = sorted(ids)
        assert out != ids, "测试前提：原始顺序本身不能恰好是字典序"
        return out
    if kind == "shuffled":
        perm = np.random.RandomState(7).permutation(len(ids))
        return [ids[i] for i in perm]
    if kind == "swap10pct":
        out = list(ids)
        n = max(1, len(out) // 10)
        for k in range(n):
            i, j = k, len(out) - 1 - k
            out[i], out[j] = out[j], out[i]
        return out
    if kind == "one_off":
        out = list(ids)
        out[7] = "99999999" if out[7].isdigit() else "BAD_SIG_ID_000"
        return out
    raise ValueError(kind)


def _rewrite_roster(d, side, ids):
    if side == "row":
        pd.DataFrame({"gene_id": ids}).to_csv(d / "row_gene_ids.csv", index=False)
    else:
        pd.DataFrame({"sig_id": ids}).to_csv(d / "col_sig_ids.csv", index=False)


def _run_check(d, mode):
    return check_startup(
        matrix_path=str(d / "fast_matrix.npy"),
        row_csv_path=str(d / "row_gene_ids.csv"),
        col_csv_path=str(d / "col_sig_ids.csv"),
        mode=mode,
        gctx_path=str(d / "tiny.gctx"),
        row_label="row_gene_ids.csv",
        col_label="col_sig_ids.csv",
    )


# ---------------------------------------------------------------------------
# 防线1：5 种花名册 × 行/列 × 2 种模式（共 20 用例，正确 4 例 + 拒绝 16 例）
# ---------------------------------------------------------------------------

TAMPERS = ["correct", "sorted", "shuffled", "swap10pct", "one_off"]


@pytest.mark.parametrize("mode", ["fingerprint", "gctx"])
@pytest.mark.parametrize("side", ["row", "col"])
@pytest.mark.parametrize("tamper", TAMPERS)
def test_roster_tampering(tmp_path, mode, side, tamper):
    d, row_ids, col_ids = _make_data_dir(tmp_path)
    original = row_ids if side == "row" else col_ids
    _rewrite_roster(d, side, _tamper(original, tamper))

    if tamper == "correct":
        report = _run_check(d, mode)
        assert report["mode"] == mode
        assert report["checked"]
    else:
        with pytest.raises(RuntimeError):
            _run_check(d, mode)


def test_gctx_mode_reports_first_mismatch_position(tmp_path):
    """错误信息必须给出第一个不一致的位置和修复命令。"""
    d, row_ids, col_ids = _make_data_dir(tmp_path)
    bad = list(row_ids)
    bad[5] = "99999999"
    _rewrite_roster(d, "row", bad)

    with pytest.raises(RuntimeError) as excinfo:
        _run_check(d, "gctx")
    msg = str(excinfo.value)
    assert "第 5 行" in msg
    assert "row_gene_ids.csv" in msg
    assert "fix_col_names.py" in msg


def test_missing_one_row_rejected(tmp_path):
    """行花名册少一行 → 行数不一致，拒绝启动。"""
    d, row_ids, col_ids = _make_data_dir(tmp_path)
    _rewrite_roster(d, "row", row_ids[:-1])
    for mode in ("fingerprint", "gctx"):
        with pytest.raises(RuntimeError, match="行数"):
            _run_check(d, mode)


# ---------------------------------------------------------------------------
# 防线1：指纹模式特有场景
# ---------------------------------------------------------------------------

def test_matrix_swap_same_shape_rejected(tmp_path):
    """指纹模式下矩阵被换成同形状的另一个文件 → 拒绝启动。"""
    d, row_ids, col_ids = _make_data_dir(tmp_path, matrix_seed=42)
    # 同形状、不同数值的矩阵覆盖原文件
    _write_matrix(d / "fast_matrix.npy", seed=999)

    with pytest.raises(RuntimeError, match="矩阵"):
        _run_check(d, "fingerprint")


def test_missing_fingerprint_rejected(tmp_path):
    d, row_ids, col_ids = _make_data_dir(tmp_path, with_fingerprint=False)
    with pytest.raises(RuntimeError) as excinfo:
        _run_check(d, "fingerprint")
    msg = str(excinfo.value)
    assert "integrity.json" in msg
    assert "fix_col_names.py" in msg  # 给出修复命令


def test_off_mode_passes_with_warning(tmp_path, caplog):
    """off 仅供测试：花名册错位也放行，但必须打 WARNING。"""
    d, row_ids, col_ids = _make_data_dir(tmp_path)
    _rewrite_roster(d, "col", _tamper(col_ids, "shuffled"))

    with caplog.at_level("WARNING", logger="lincs_integrity"):
        report = _run_check(d, "off")
    assert report["mode"] == "off"
    assert any(
        r.levelname == "WARNING" and "仅供测试" in r.getMessage()
        for r in caplog.records
    )


def test_trailing_blank_line_tolerated_with_warning(tmp_path, caplog):
    """文件末尾多一个空行：按约定容忍，但必须有明确日志，不能静默。"""
    d, row_ids, col_ids = _make_data_dir(tmp_path)
    with open(d / "col_sig_ids.csv", "ab") as f:
        f.write(b"\r\n")

    with caplog.at_level("WARNING", logger="lincs_integrity"):
        report = _run_check(d, "fingerprint")
    assert report["mode"] == "fingerprint"
    assert any("空行" in r.getMessage() for r in caplog.records)


def test_invalid_mode_rejected(tmp_path):
    d, row_ids, col_ids = _make_data_dir(tmp_path)
    with pytest.raises(RuntimeError, match="LINCS_INTEGRITY_MODE"):
        _run_check(d, "sometimes")


# ---------------------------------------------------------------------------
# 防线2：判档规则 4.5（landmark 自身 KS > 0 → 最高黄档）
# ---------------------------------------------------------------------------

def _grade_sig(self_ks, n_sig=30, loho=0.8):
    return {
        "gene_name": "G",
        "n_sig": n_sig,
        "up_genes": ["U1", "U2"],
        "down_genes": ["D1", "D2"],
        "fast_mode": False,
        "ks_scores": {"G": self_ks, "U1": 0.4, "D1": -0.4},
        "target_median_z": -1.0,
        "loho_jaccard_min": loho,
        "loho_detail": {"k": 10, "n_hairpins": 3,
                        "n_hairpins_used": 3, "n_hairpins_skipped": 0},
    }


def _grade_pre():
    return {
        "gene_name": "G", "n_samples": 10, "n_hairpins": 3, "n_cells": 4,
        "cell_lines": ["A375"], "data_gate_ok": True, "reasons": ["ok"],
    }


def test_self_ks_positive_caps_green_at_yellow():
    import suitability
    from suitability import grade

    result = grade(_grade_sig(self_ks=0.5), _grade_pre())
    assert result["grade"] == "yellow"
    assert result["rule_version"] == "4.5"
    assert suitability.RULE_VERSION == "4.5"
    assert any(
        "敲低后目标基因自身未下降" in r and "敲低可能未生效或数据有误" in r
        for r in result["reasons"]
    )


def test_self_ks_negative_keeps_green():
    from suitability import grade

    result = grade(_grade_sig(self_ks=-0.5), _grade_pre())
    assert result["grade"] == "green"


def test_self_ks_positive_does_not_change_red():
    from suitability import grade

    # n_sig < 5 本来就是红档；自身 KS > 0 不会"升档"
    result = grade(_grade_sig(self_ks=0.5, n_sig=3), _grade_pre())
    assert result["grade"] == "red"


# ---------------------------------------------------------------------------
# 防线2：哨兵生物学自检（stub provider）
# ---------------------------------------------------------------------------

class _StubProvider:
    """3 个 landmark 基因、每个 3 hairpin × 2 样本。

    knocked_down=True 的基因在自身样本里表达最低（自身 KS 强负 → 自检通过）；
    knocked_down=False 则表达最高（自身 KS 强正 → 自检不通过，模拟行错位）。
    """

    def __init__(self, knocked_down):
        self._genes = list(knocked_down)
        self._down = dict(knocked_down)
        rng = np.random.RandomState(0)
        self._sigs = []
        self._cols = {}
        for g in self._genes:
            cols = []
            for h in range(3):
                for rep in range(2):
                    sid = "%s_H%d_%d" % (g, h, rep)
                    vec = rng.standard_normal(len(self._genes)).astype(np.float32)
                    vec[self._genes.index(g)] = -3.0 if self._down[g] else 3.0
                    self._cols[sid] = vec
                    cols.append((sid, "H%d" % h))
                    self._sigs.append((g, sid, "H%d" % h))
        rows = [
            {"sig_id": sid, "pert_id": "%s_%s" % (g, hp), "pert_iname": g,
             "cell_id": "A375", "pert_type": "trt_sh"}
            for g, sid, hp in self._sigs
        ]
        self._sh = pd.DataFrame(rows)

    def get_shrna_samples(self, gene_name):
        return self._sh[self._sh["pert_iname"] == gene_name.upper()].copy()

    def get_gene_symbols(self):
        return list(self._genes)

    def get_expression_matrix(self, sig_ids):
        return np.stack([self._cols[s] for s in sig_ids], axis=1)


def test_self_check_ok():
    import integrity_selfcheck

    provider = _StubProvider({"CDK4": True, "PCNA": True, "MYC": True})
    result = integrity_selfcheck.run_self_check(provider, ["CDK4", "PCNA", "MYC"])
    assert result["status"] == "ok"
    assert result["n_checked"] == 3
    assert result["n_failed"] == 0
    assert all(r["self_ks"] < -0.3 for r in result["results"])


def test_self_check_suspect_when_two_of_three_fail():
    import integrity_selfcheck

    provider = _StubProvider({"CDK4": False, "PCNA": False, "MYC": True})
    result = integrity_selfcheck.run_self_check(provider, ["CDK4", "PCNA", "MYC"])
    assert result["status"] == "suspect"
    assert result["n_failed"] == 2


def test_self_check_ok_when_only_one_of_three_fails():
    import integrity_selfcheck

    provider = _StubProvider({"CDK4": False, "PCNA": True, "MYC": True})
    result = integrity_selfcheck.run_self_check(provider, ["CDK4", "PCNA", "MYC"])
    assert result["status"] == "ok"


def test_self_check_unknown_when_no_sentinel_available():
    import integrity_selfcheck

    provider = _StubProvider({"CDK4": True})
    result = integrity_selfcheck.run_self_check(provider, ["PCNA", "MYC"])
    assert result["status"] == "unknown"
    assert result["n_checked"] == 0


@requires_fixture
def test_health_integrity_field_reflects_state(monkeypatch):
    """/api/health 的 integrity 字段由自检状态驱动。"""
    import integrity_selfcheck
    from fastapi.testclient import TestClient
    import main as main_module

    monkeypatch.setitem(integrity_selfcheck.STATE, "status", "suspect")
    client = TestClient(main_module.app)
    body = client.get("/api/health").json()
    assert body["integrity"] == "suspect"
    assert body["integrity_mode"] in ("gctx", "fingerprint", "off")


# ---------------------------------------------------------------------------
# 夹具回归：CDK4 结果不变；伪签名判黄档；哨兵自检通过
# ---------------------------------------------------------------------------

def _cdk4_baseline():
    """按当前生效夹具读取 CDK4 基准（n_sig / LOHO）。

    D2 后默认夹具是仓库内置 mini（CDK4 n_sig=230），LMNA_FIXTURE_DIR 指向
    24MB 完整夹具时为 234；两套夹具各自随带 lmna_fixture_expected.json，
    基准从生效夹具的 expected 读取，缺失键时回落到完整夹具基线。
    """
    n_sig, loho = 234, 0.587
    if FIXTURE_DIR:
        path = os.path.join(FIXTURE_DIR, "lmna_fixture_expected.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f).get("CDK4", {})
            n_sig = entry.get("n_sig", n_sig)
            loho = entry.get("target_loho", loho)
    return n_sig, loho


@requires_fixture
def test_fixture_cdk4_unchanged_and_fake_signature_yellow():
    import signature_engine as se
    from fixture_provider import FixtureProvider
    from suitability import grade, precheck

    saved = (se.BOOTSTRAP_N, se.FAST_MODE_TOP_N, se.MAX_GENES_PER_DIRECTION)
    se.BOOTSTRAP_N = 1000
    se.FAST_MODE_TOP_N = 0
    se.MAX_GENES_PER_DIRECTION = 50
    try:
        provider = FixtureProvider()
        sig = se.SignatureEngine(provider).compute_signature("CDK4")
    finally:
        (se.BOOTSTRAP_N, se.FAST_MODE_TOP_N, se.MAX_GENES_PER_DIRECTION) = saved

    # 基线按当前生效夹具的 expected 读取（完整夹具 234/0.587，mini 230/0.5873），
    # 判档绿、rule_version、自身 KS 要求与夹具无关
    expected_n_sig, expected_loho = _cdk4_baseline()
    assert sig["n_sig"] == expected_n_sig
    assert abs(sig["loho_jaccard_min"] - expected_loho) <= 0.05
    assert sig["qc"]["grade"] == "green"
    assert sig["qc"]["rule_version"] == "4.5"
    assert sig["ks_scores"]["CDK4"] < -0.3

    # 人为把 CDK4 自身 KS 改成正值的伪签名 → 最高黄档
    fake = copy.deepcopy(sig)
    fake["ks_scores"]["CDK4"] = abs(sig["ks_scores"]["CDK4"])
    verdict = grade(fake, precheck(provider, "CDK4"))
    assert verdict["grade"] == "yellow"
    assert any("敲低可能未生效或数据有误" in r for r in verdict["reasons"])


@requires_fixture
def test_fixture_sentinel_self_check_ok():
    import integrity_selfcheck
    from fixture_provider import FixtureProvider

    provider = FixtureProvider()
    # 夹具中只有 CDK4 是可用哨兵（PCNA/MYC 不在夹具 shRNA 表中，会被跳过）
    result = integrity_selfcheck.run_self_check(provider, ["CDK4", "PCNA", "MYC"])
    assert result["status"] == "ok"
    cdk4 = [r for r in result["results"] if r["gene"] == "CDK4"][0]
    assert cdk4["checked"] is True
    assert cdk4["self_ks"] < -0.3

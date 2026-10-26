#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7e 阶段 2 单元测试：robust z 口径、L3Provider、CompositeProvider、
缓存键隔离、NaN 剔除。全部使用合成小矩阵（3–4 板、每板 2–5 对照、
20 基因），不依赖服务器数据。
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from l3_robust_z import (
    MIN_CTL_PER_PLATE, EPS_SCALE, SCALE_FLOOR_REL, MAD_TO_SD,
    RANK_NAN_SENTINEL, plate_robust_stats, resolve_control_stats,
    apply_robust_z, rank_columns_nanaware,
)
from l3_provider import L3Provider, _sha256_lines

BACKEND_DIR = Path(__file__).resolve().parents[1]


# =====================================================================
# 1. robust z 纯函数
# =====================================================================

def test_plate_robust_stats_hand_calc():
    """手算对照：median / MAD / 1.4826。"""
    # 5 个对照 × 2 基因；gene0: med=0, MAD=1 → raw=1.4826；
    # gene1: med=5, MAD=2 → raw=2.9652
    vals = np.array([
        [0.0, 5.0],
        [1.0, 7.0],
        [-1.0, 3.0],
        [2.0, 9.0],
        [-2.0, 1.0],
    ])
    median, scale, bad = plate_robust_stats(vals)
    np.testing.assert_allclose(median, [0.0, 5.0], atol=1e-12)
    raw_expected = np.array([1.0, 2.0]) * MAD_TO_SD
    floor = float(np.median(raw_expected)) * SCALE_FLOOR_REL
    np.testing.assert_allclose(
        scale, np.maximum(raw_expected, floor), rtol=1e-12)
    assert not bad.any()
    # floor 不绑定（raw 都远大于 floor）
    np.testing.assert_allclose(scale, raw_expected, rtol=1e-12)


def test_scale_floor_caps_tiny_mad():
    """tiny-MAD 防爆：scale = max(1.4826*MAD, 同板 scale 中位数×0.01)。"""
    # gene0/gene1 MAD=1（raw 1.4826）；gene2 MAD=1e-6（raw 1.4826e-6）
    base = np.array([0.0, 1.0, -1.0, 2.0, -2.0])
    vals = np.column_stack([base, base, base * 1e-6])
    median, scale, bad = plate_robust_stats(vals)
    raws = np.array([MAD_TO_SD, MAD_TO_SD, MAD_TO_SD * 1e-6])
    floor = float(np.median(raws)) * SCALE_FLOOR_REL
    assert floor > raws[2]                      # 确认本例 floor 绑定
    assert scale[2] == pytest.approx(floor)
    assert not bad.any()                        # tiny 但非 0：不置 NaN
    # z 被 floor 限幅：x=1.0 时 z=(1-0)/floor ≈ 67.4，而非 ~67 万
    z = apply_robust_z(np.array([1.0, 1.0, 1.0]), median, scale, bad)
    assert z[2] == pytest.approx(1.0 / floor, rel=1e-5)
    assert abs(z[2]) < 1000


def test_mad_zero_gene_set_to_nan():
    """MAD=0（同板对照全同值）→ bad_mask → z 置 NaN。"""
    vals = np.array([
        [0.0, 3.0],
        [1.0, 3.0],
        [-1.0, 3.0],
        [2.0, 3.0],
    ])
    median, scale, bad = plate_robust_stats(vals)
    assert bad.tolist() == [False, True]
    z = apply_robust_z(np.array([5.0, 9.0]), median, scale, bad)
    assert np.isfinite(z[0]) and np.isnan(z[1])


def test_resolve_control_stats_fallback_levels():
    """对照 <3 回退：同板 → 同细胞系 → 全局。"""
    good = plate_robust_stats(np.random.default_rng(1).normal(size=(4, 5)))
    few = plate_robust_stats(np.random.default_rng(2).normal(size=(2, 5)))
    cell = plate_robust_stats(np.random.default_rng(3).normal(size=(6, 5)))
    glob = plate_robust_stats(np.random.default_rng(4).normal(size=(50, 5)))
    plate_stats = {"P_OK": (*good, 4), "P_FEW": (*few, 2)}
    cell_stats = {"CA": (*cell, 6), "CB": (*few, 2)}
    global_stats = (*glob, 50)

    # level 0：同板对照充足
    _, _, _, lvl = resolve_control_stats(
        "P_OK", "CA", plate_stats, cell_stats, global_stats)
    assert lvl == 0
    # level 1：板 <3 → 同细胞系（CA 有 6 个）
    med, _, _, lvl = resolve_control_stats(
        "P_FEW", "CA", plate_stats, cell_stats, global_stats)
    assert lvl == 1
    np.testing.assert_array_equal(med, cell[0])
    # level 2：细胞系也不足 → 全局
    med, _, _, lvl = resolve_control_stats(
        "P_FEW", "CB", plate_stats, cell_stats, global_stats)
    assert lvl == 2
    np.testing.assert_array_equal(med, glob[0])
    # 板完全无对照 → 同细胞系
    _, _, _, lvl = resolve_control_stats(
        "P_NONE", "CA", plate_stats, cell_stats, global_stats)
    assert lvl == 1


def test_rank_columns_nanaware():
    """NaN 剔除排名：NaN → 哨兵 0，有限值占 1..k；无 NaN 与旧口径一致。"""
    expr = np.array([
        [5.0, 1.0],
        [np.nan, 4.0],
        [1.0, np.nan],
        [3.0, 2.0],
    ])
    ranks = rank_columns_nanaware(expr)
    assert ranks.dtype == np.int16
    # 列 0：5.0 最高秩 1，3.0 秩 2，1.0 秩 3，NaN 哨兵 0
    assert ranks[:, 0].tolist() == [1, RANK_NAN_SENTINEL, 3, 2]
    # 列 1：4.0 秩 1，2.0 秩 2，1.0 秩 3，NaN 哨兵 0
    assert ranks[:, 1].tolist() == [3, 1, RANK_NAN_SENTINEL, 2]

    clean = np.arange(12, dtype=np.float64).reshape(4, 3) % 7
    legacy = np.argsort(np.argsort(-clean, axis=0), axis=0).astype(np.int16) + 1
    np.testing.assert_array_equal(rank_columns_nanaware(clean), legacy)


# =====================================================================
# 2. 合成 L3 派生层 + L3Provider
# =====================================================================

N_GENES = 20
SYMBOLS = [f"G{i:02d}" for i in range(N_GENES)]
ENTREZ = [str(1000 + i) for i in range(N_GENES)]


def _build_derived_dir(root: Path) -> dict:
    """
    合成派生层：4 板（P1/P2/P3 属 CELL_A，P4 属 CELL_B），
    对照数 4/3/2/2（P3 回退 L1，P4 回退 L2），含 1 行 trt_sh.cgs 诱饵。
    """
    rng = np.random.default_rng(7)
    rows = []

    def add(plate, cell, ptype, prefix, n, pert_iname="", pert_id=""):
        for j in range(n):
            rows.append({
                "inst_id": f"{prefix}_{plate}_{j}",
                "rna_plate": plate, "cell_id": cell, "pert_type": ptype,
                "pert_iname": pert_iname, "pert_id": pert_id,
            })

    add("P1", "CELL_A", "ctl_vector", "CTL", 4)
    add("P1", "CELL_A", "trt_sh", "SH", 3, "GENEA", "H1")
    rows[-1]["pert_id"] = "H2"          # GENEA: P1 含 H1×2 + H2×1
    add("P2", "CELL_A", "ctl_vector", "CTL", 3)
    add("P2", "CELL_A", "trt_sh", "SH", 2, "GENEB", "H3")
    rows[-1]["pert_id"] = "H4"
    add("P3", "CELL_A", "ctl_vector", "CTL", 2)
    add("P3", "CELL_A", "trt_sh", "SH", 1, "GENEA", "H2")
    add("P4", "CELL_B", "ctl_vector", "CTL", 2)
    add("P4", "CELL_B", "trt_sh", "SH", 1, "GENEB", "H3")
    add("P2", "CELL_A", "trt_sh.cgs", "CGS", 1, "GENEA", "H1")  # 诱饵

    n = len(rows)
    z = rng.normal(size=(n, N_GENES)).astype(np.float32)
    plate_n_ctl = {"P1": 4, "P2": 3, "P3": 2, "P4": 2}
    plate_lvl = {"P1": 0, "P2": 0, "P3": 1, "P4": 2}
    meta = pd.DataFrame(rows)
    meta["n_controls"] = meta["rna_plate"].map(plate_n_ctl)
    meta["fallback_level"] = meta["rna_plate"].map(plate_lvl).astype(np.int8)

    root.mkdir(parents=True, exist_ok=True)
    np.save(root / "l3_landmark.npy", z)
    meta[["inst_id", "rna_plate", "pert_id", "pert_iname", "cell_id",
          "pert_type", "n_controls", "fallback_level"]].to_csv(
        root / "instance_meta.csv", index=False)
    col_ids = meta["inst_id"].tolist()
    (root / "col_ids.txt").write_text(
        "\n".join(col_ids) + "\n", encoding="utf-8")
    pd.DataFrame({"entrez_id": ENTREZ, "gene_symbol": SYMBOLS}).to_csv(
        root / "row_genes.csv", index=False)
    manifest = {
        "derived_version": "l3_v1",
        "matrix": {
            "shape": [n, N_GENES],
            "col_ids_sha256": _sha256_lines(col_ids),
            "row_genes_sha256": _sha256_lines(
                [f"{e},{s}" for e, s in zip(ENTREZ, SYMBOLS)]),
        },
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"meta": meta, "z": z, "col_ids": col_ids}


@pytest.fixture()
def derived(tmp_path):
    root = tmp_path / "l3_v1"
    info = _build_derived_dir(root)
    return root, info


def test_l3_provider_trt_sh_exact_match(derived):
    """pert_type == 'trt_sh' 精确匹配：trt_sh.cgs 诱饵不得混入。"""
    root, info = derived
    p = L3Provider(str(root))
    all_sh = p.get_all_shrna_samples()
    assert (all_sh["pert_type"] == "trt_sh").all()
    assert len(all_sh) == 7                      # 3+2+1+1，cgs 诱饵被排除
    genea = p.get_shrna_samples("genea")         # 大小写不敏感
    assert len(genea) == 4
    assert sorted(genea["pert_id"].unique()) == ["H1", "H2"]
    # sig_id = inst_id（实例级口径）
    assert (genea["sig_id"] == genea["inst_id"]).all()


def test_l3_provider_expression_matrix_orientation(derived):
    root, info = derived
    p = L3Provider(str(root))
    ids = info["col_ids"][:5]
    mat = p.get_expression_matrix(ids)
    assert mat.shape == (N_GENES, 5)             # (978→G, n) 列=样本
    np.testing.assert_allclose(mat, info["z"][:5].T, rtol=1e-6)
    with pytest.raises(KeyError):
        p.get_expression_matrix(["NO_SUCH_INST"])


def test_l3_provider_misc_methods(derived):
    root, info = derived
    p = L3Provider(str(root))
    assert p.get_gene_symbols() == SYMBOLS
    np.testing.assert_array_equal(
        p.get_lm_gene_indices(), np.arange(N_GENES, dtype=np.int32))
    assert p.list_available_genes() == ["GENEA", "GENEB"]
    veh = p.get_vehicle_samples_for_plate("P1")
    assert len(veh) == 4 and all(v.startswith("CTL_P1") for v in veh)
    assert p.get_vehicle_samples_for_plate("NOPE") == []
    for fn in (p.get_drug_samples, p.get_drug_name_map):
        with pytest.raises(NotImplementedError):
            fn()
    with pytest.raises(NotImplementedError):
        p.get_drug_expression_matrix(["x"])


def test_l3_provider_refuses_tampered_col_ids(derived):
    """行 ID 花名册与 manifest 不一致 → 拒绝启动。"""
    root, info = derived
    ids = info["col_ids"][:]
    ids[0], ids[1] = ids[1], ids[0]
    (root / "col_ids.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="manifest"):
        L3Provider(str(root))


def test_l3_provider_refuses_row_count_mismatch(derived):
    root, info = derived
    meta = pd.read_csv(root / "instance_meta.csv", dtype=str)
    meta.iloc[:-1].to_csv(root / "instance_meta.csv", index=False)
    with pytest.raises(RuntimeError):
        L3Provider(str(root))


def test_l3_provider_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError, match="派生层"):
        L3Provider(str(tmp_path / "nope"))


# =====================================================================
# 3. 缓存键隔离（L3/L5 签名缓存文件名不同）
# =====================================================================

def test_cache_key_isolation_l3_vs_l5(monkeypatch):
    import config
    from cache_manager import CacheManager, signature_params_hash

    hash_l5 = signature_params_hash()
    path_l5 = CacheManager.signature_path("CDK4")

    monkeypatch.setattr(config, "DATA_PROVIDER", "l3")
    monkeypatch.setattr(config, "SIGNATURE_AGGREGATION", "instance")
    params_l3 = config.signature_params()
    assert params_l3["DATA_PROVIDER"] == "l3"
    assert params_l3["aggregation"] == "instance"
    hash_l3 = signature_params_hash()
    path_l3 = CacheManager.signature_path("CDK4")

    assert hash_l3 != hash_l5
    assert path_l3 != path_l5
    assert hash_l5 in os.path.basename(path_l5)
    assert hash_l3 in os.path.basename(path_l3)


def test_signature_params_has_aggregation_field():
    import config
    params = config.signature_params()
    assert "DATA_PROVIDER" in params
    assert "aggregation" in params
    # 测试会话 DATA_PROVIDER=fixture（conftest）→ 非 l3 一律 modz
    assert params["aggregation"] == "modz"


# =====================================================================
# 4. CompositeProvider 路由
# =====================================================================

class _FakeSig:
    def __init__(self, symbols):
        self._symbols = list(symbols)
        self.root = "fake-l3"

    def get_gene_symbols(self):
        return list(self._symbols)

    def get_shrna_samples(self, gene_name):
        return pd.DataFrame({"sig_id": ["sig-side"], "pert_iname": [gene_name]})

    def get_all_shrna_samples(self):
        return pd.DataFrame({"sig_id": ["sig-side"]})

    def get_expression_matrix(self, sig_ids):
        return np.ones((len(self._symbols), len(sig_ids)), dtype=np.float32)

    def get_lm_gene_indices(self):
        return np.arange(len(self._symbols), dtype=np.int32)

    def get_vehicle_samples_for_plate(self, plate_id):
        return [f"ctl-of-{plate_id}"]

    def list_available_genes(self):
        return ["GENEA"]


class _FakeDrug:
    def __init__(self, symbols):
        self._symbols = list(symbols)

    def get_gene_symbols(self):
        return list(self._symbols)

    def get_drug_samples(self):
        return pd.DataFrame({"sig_id": ["drug-side"]})

    def get_drug_expression_matrix(self, sig_ids):
        return np.zeros((len(self._symbols), len(sig_ids)), dtype=np.float32)

    def get_drug_name_map(self):
        return pd.Series({"drug-side": "drugA"})


def test_composite_provider_routing():
    from composite_provider import CompositeProvider
    cp = CompositeProvider(signature_provider=_FakeSig(["A", "B"]),
                           drug_provider=_FakeDrug(["A", "B"]))
    # 签名侧
    assert cp.get_shrna_samples("X")["sig_id"].tolist() == ["sig-side"]
    assert cp.get_all_shrna_samples()["sig_id"].tolist() == ["sig-side"]
    assert cp.get_expression_matrix(["s"]).shape == (2, 1)
    assert cp.get_gene_symbols() == ["A", "B"]
    assert cp.get_lm_gene_indices().tolist() == [0, 1]
    assert cp.get_vehicle_samples_for_plate("P9") == ["ctl-of-P9"]
    assert cp.list_available_genes() == ["GENEA"]
    # 药物侧
    assert cp.get_drug_samples()["sig_id"].tolist() == ["drug-side"]
    assert cp.get_drug_expression_matrix(["d"]).shape == (2, 1)
    assert cp.get_drug_name_map().to_dict() == {"drug-side": "drugA"}


# =====================================================================
# 5. SignatureEngine NaN 剔除（合成 20 基因小池）
# =====================================================================

class _NaNPoolProvider:
    """20 基因 × 13 个 shRNA 样本的合成 provider。

    目标基因 TG 4 个样本（2 hairpin × 2 细胞系）；
    基因 G03 在 1 个目标样本中为 NaN；G05 只在背景样本中为 NaN。
    """

    G = N_GENES

    def __init__(self):
        rng = np.random.default_rng(11)
        self._symbols = SYMBOLS
        n = 13
        self._df = pd.DataFrame({
            "sig_id": [f"S{i}" for i in range(n)],
            "pert_id": (["H1", "H1", "H2", "H2"]
                        + [f"HX{i}" for i in range(9)]),
            "pert_iname": ["TG"] * 4 + [f"BG{i}" for i in range(9)],
            "cell_id": ["CA", "CB", "CA", "CB"] + ["CA"] * 9,
            "pert_type": ["trt_sh"] * n,
        })
        self._mat = rng.normal(size=(self.G, n)).astype(np.float32)
        self._mat[3, 0] = np.nan        # G03 在目标样本 S0 为 NaN
        self._mat[5, 7] = np.nan        # G05 仅在背景样本 S7 为 NaN
        self._mat[5, 9] = np.nan

    def get_shrna_samples(self, gene_name):
        df = self._df[self._df["pert_iname"] == gene_name.upper()]
        return df.copy()

    def get_all_shrna_samples(self):
        return self._df.copy()

    def get_expression_matrix(self, sig_ids):
        idx = [self._df.index[self._df["sig_id"] == s][0] for s in sig_ids]
        return self._mat[:, idx]

    def get_gene_symbols(self):
        return list(self._symbols)


def test_engine_excludes_nan_genes(tmp_path, monkeypatch):
    import signature_engine as se

    # 秩缓存指向本测试独占路径，避免与共享缓存目录里的同尺寸缓存串扰
    monkeypatch.setattr(se, "_SHRNA_RANK_CACHE", str(tmp_path / "rank.dat"))
    monkeypatch.setattr(se, "_SHRNA_RANK_SHAPE", str(tmp_path / "rank.shape.txt"))

    engine = se.SignatureEngine(_NaNPoolProvider())
    sig = engine.compute_signature("TG")

    assert sig["n_samples"] == 4
    # G03（目标内 NaN）与 G05（池内 NaN）都被剔除
    assert sig["excluded_nan_genes"] == ["G03", "G05"]
    assert sig["n_excluded_nan_genes"] == 2
    assert "G03" not in sig["up_genes"] and "G03" not in sig["down_genes"]
    assert "G05" not in sig["up_genes"] and "G05" not in sig["down_genes"]
    assert sig["ks_scores"]["G03"] is None
    assert sig["fdr_values"]["G05"] is None
    # 其余基因正常出数
    assert isinstance(sig["ks_scores"]["G00"], float)
    assert isinstance(sig["fdr_values"]["G00"], float)
    assert sig["all_ks"][3] is None and sig["all_p"][5] is None
    assert isinstance(sig["all_ks"][0], float)
    # n_sig 与 up/down 一致（剔除基因不占额度）
    assert sig["n_sig"] == len(sig["up_genes"]) + len(sig["down_genes"])

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L2 缓存失效与版本化测试。

覆盖三条验收：
1. 改变 KS_THRESHOLD 后生成新缓存文件，不读旧文件；
2. 两个线程并发写 1000 次 + 并发读，读取方不会读到半截 JSON；
3. multiprocessing 两个进程同时构建秩缓存，最终文件可读且只构建一次。
"""

import contextlib
import json
import multiprocessing
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]


# ==================== 1. 参数变化 → 新缓存文件 ====================

def test_signature_params_contains_algo_version():
    import config

    params = config.signature_params()
    assert params["ALGO_VERSION"] == config.ALGO_VERSION == "2"
    for key in (
        "DATA_PROVIDER",
        "KS_THRESHOLD",
        "FDR_THRESHOLD",
        "BOOTSTRAP_N",
        "RANDOM_SEED",
        "FAST_MODE_TOP_N",
        "MAX_GENES_PER_DIRECTION",
        "DRUG_NULL_N",  # L4 药物 p 值参数，确保改 N 后药物缓存失效
    ):
        assert key in params


def test_ks_threshold_change_generates_new_cache_file(monkeypatch):
    import config
    from cache_manager import CacheManager, signature_params_hash

    gene = "L2PARAM"
    cache = CacheManager()

    hash_before = signature_params_hash()
    cache.save_signature(gene, {"gene_name": gene, "version": 1})
    path_before = cache.signature_path(gene)
    assert os.path.exists(path_before)
    assert hash_before in os.path.basename(path_before)

    # 改变 KS_THRESHOLD：哈希变化，旧文件不应被读到。
    monkeypatch.setattr(config, "KS_THRESHOLD", config.KS_THRESHOLD + 0.05)
    hash_after = signature_params_hash()
    assert hash_after != hash_before
    assert cache.get_signature(gene) is None
    assert not cache.signature_exists(gene)

    cache.save_signature(gene, {"gene_name": gene, "version": 2})
    path_after = cache.signature_path(gene)
    assert path_after != path_before
    assert os.path.exists(path_after)

    data = cache.get_signature(gene)
    assert data is not None and data["version"] == 2

    # list_cached_genes 解析新文件名并去重（同一基因两个版本只出现一次）。
    assert cache.list_cached_genes().count(gene) == 1

    # clear_gene 用 glob 删除该基因的所有版本。
    assert cache.clear_gene(gene) is True
    assert not os.path.exists(path_before)
    assert not os.path.exists(path_after)
    assert gene not in cache.list_cached_genes()

    cache.clear_gene(gene)  # 清理干净后再删不应报错


def test_drug_cache_filename_contains_hash_method_and_mode():
    from cache_manager import CacheManager, signature_params_hash

    cache = CacheManager()
    h = signature_params_hash()
    # L2 × L3 统一命名：{GENE}_{h}_{method}_{fast_mode}_{score_mode}_drug_scores.json
    fast_lof = cache.drug_scores_path(
        "L2DRUG", "XSUM", fast_mode="fast", score_mode="lof"
    )
    normal_gof = cache.drug_scores_path(
        "L2DRUG", "xsum", fast_mode="normal", score_mode="gof"
    )
    assert h in os.path.basename(fast_lof)
    assert os.path.basename(fast_lof).endswith("_xsum_fast_lof_drug_scores.json")
    assert os.path.basename(normal_gof).endswith("_xsum_normal_gof_drug_scores.json")
    assert fast_lof != normal_gof

    cache.save_drug_scores(
        "L2DRUG", "xsum", {"method": "xsum"}, score_mode="lof", fast_mode="fast"
    )
    # 查找时不指定 fast_mode 会回退到同哈希/同 score_mode 下的 fast 文件。
    assert cache.get_drug_scores("L2DRUG", "xsum", mode="lof")["method"] == "xsum"
    assert cache.clear_gene("L2DRUG") is True


# ==================== 2. 并发写读：不出现半截 JSON ====================

def test_concurrent_writes_never_produce_partial_json():
    from cache_manager import CacheManager

    gene = "L2CONC"
    cache = CacheManager()
    path = cache.signature_path(gene)

    n_writers = 2
    writes_per_writer = 500  # 合计 1000 次写入
    read_errors = []
    reads = 0
    stop = threading.Event()

    def writer(writer_id):
        for i in range(writes_per_writer):
            cache.save_signature(gene, {
                "gene_name": gene,
                "writer": writer_id,
                "i": i,
                "payload": "x" * 512,
            })

    def reader():
        nonlocal reads
        while not stop.is_set():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                assert "i" in data and data["payload"] == "x" * 512
                reads += 1
            except FileNotFoundError:
                pass  # 首次写入前
            except PermissionError:
                # Windows 上 os.replace 替换目标的瞬间，新的 open 可能短暂被拒；
                # 这与 JSON 完整性无关，稍后重试。
                time.sleep(0.001)
            except json.JSONDecodeError as exc:
                read_errors.append(exc)

    readers = [threading.Thread(target=reader) for _ in range(2)]
    writers = [
        threading.Thread(target=writer, args=(i,)) for i in range(n_writers)
    ]

    for t in readers:
        t.start()
    for t in writers:
        t.start()
    for t in writers:
        t.join(timeout=120)
    stop.set()
    for t in readers:
        t.join(timeout=30)

    assert not read_errors, f"读到半截 JSON: {read_errors[:3]}"
    assert reads > 0
    with open(path, "r", encoding="utf-8") as f:
        assert json.load(f)["gene_name"] == gene
    cache.clear_gene(gene)


# ==================== 3. multiprocessing：秩缓存只构建一次 ====================

def _rank_cache_worker(cache_dir, backend_dir, log_path, barrier):
    """子进程：设置独立缓存目录后并发构建秩缓存。"""
    os.environ["LMNA_CACHE_DIR"] = cache_dir
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    import signature_engine as se

    n_sigs = 8

    class FakeProvider:
        def get_all_shrna_samples(self):
            return pd.DataFrame({"sig_id": [f"S{i}" for i in range(n_sigs)]})

        def get_gene_symbols(self):
            return [f"G{i}" for i in range(978)]

        def get_expression_matrix(self, sig_ids):
            # 拉长构建窗口，保证第二个进程会在锁上等待并做双重检查。
            time.sleep(0.2)
            values = np.arange(978 * len(sig_ids), dtype=np.float64)
            values = (values % 97).reshape(978, len(sig_ids)) + 1.0
            return values

    barrier.wait(timeout=60)
    with open(log_path, "a", encoding="utf-8") as log_file, \
            contextlib.redirect_stdout(log_file):
        se._ensure_shrna_rank_cache(FakeProvider())
        print("WORKER_DONE", flush=True)


def test_multiprocessing_rank_cache_built_once(tmp_path):
    import config

    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir, exist_ok=True)
    log_path = str(tmp_path / "rank_build.log")
    n_sigs = 8

    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(2)
    procs = [
        ctx.Process(
            target=_rank_cache_worker,
            args=(cache_dir, str(BACKEND_DIR), log_path, barrier),
        )
        for _ in range(2)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=180)

    assert all(p.exitcode == 0 for p in procs), [p.exitcode for p in procs]

    with open(log_path, "r", encoding="utf-8") as f:
        log = f.read()
    assert log.count("首次构建 shRNA 排名矩阵") == 1, log
    assert log.count("WORKER_DONE") == 2

    dat_path = os.path.join(
        cache_dir, f"_shrna_rank_matrix.v{config.ALGO_VERSION}.{n_sigs}.dat"
    )
    shape_path = os.path.join(
        cache_dir, f"_shrna_rank_matrix.v{config.ALGO_VERSION}.{n_sigs}.shape.txt"
    )
    assert os.path.exists(dat_path)
    assert os.path.exists(shape_path)
    with open(shape_path, "r", encoding="utf-8") as f:
        assert f.read().strip() == f"978,{n_sigs}"

    ranks = np.memmap(dat_path, dtype="int16", mode="r", shape=(978, n_sigs))
    assert ranks.shape == (978, n_sigs)
    assert int(ranks.min()) >= 1 and int(ranks.max()) <= 978


# ==================== 4. 药物中位数缓存同样带版本 + 锁 ====================

def test_drug_median_cache_versioned_and_built_once(tmp_path, monkeypatch):
    import config
    import drug_median_cache as dmc

    monkeypatch.setattr(dmc, "CACHE_DIR", str(tmp_path))

    calls = {"build": 0}

    class FakeProvider:
        def get_drug_samples(self):
            return pd.DataFrame({"sig_id": ["d1", "d2", "d3"]})

        def get_drug_name_map(self):
            return pd.Series({"d1": "A", "d2": "A", "d3": "B"})

        def get_drug_expression_matrix(self, sig_ids):
            calls["build"] += 1
            base = np.array([1.0, 2.0, 3.0, 4.0]).reshape(4, 1)
            return np.repeat(base, len(sig_ids), axis=1)

    matrix1, names1 = dmc._ensure_drug_median_cache(FakeProvider())
    path, names_path = dmc._drug_median_cache_paths()
    assert f"v{config.ALGO_VERSION}" in os.path.basename(path)
    assert f"v{config.ALGO_VERSION}" in os.path.basename(names_path)
    assert calls["build"] == 1
    assert names1 == ["A", "B"]
    assert matrix1.shape == (4, 2)
    assert os.path.exists(path) and os.path.exists(names_path)

    # 第二次调用直接读缓存，不再构建。
    matrix2, names2 = dmc._ensure_drug_median_cache(FakeProvider())
    assert calls["build"] == 1
    assert names2 == ["A", "B"]
    assert matrix2.shape == (4, 2)


# ==================== 5. 原子写工具本身 ====================

def test_atomic_write_json_replaces_and_cleans_temp(tmp_path):
    from cache_manager import atomic_write_json

    target = tmp_path / "sub" / "data.json"
    atomic_write_json(str(target), {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    atomic_write_json(str(target), {"a": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 2}
    leftovers = [p for p in target.parent.iterdir() if ".tmp." in p.name]
    assert leftovers == []

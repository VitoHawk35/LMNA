#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FastAPI 接口测试（需要 LMNA_FIXTURE_DIR）。"""

import os

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


@pytest.fixture(scope="module")
def client():
    # 仅在夹具可用时 import main（main 在 import 时会创建 FixtureProvider）
    from fastapi.testclient import TestClient
    import main as main_module

    return TestClient(main_module.app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["provider"] == "fixture"
    assert body["available_genes"] >= 4


def test_frontend_served_at_root(client):
    """L5：前端与 API 同源部署，"/" 返回 index.html 且不遮蔽 /api。"""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "基因敲低签名与药物筛选" in resp.text
    # 同一 TestClient 下 API 路由仍然优先
    assert client.get("/api/health").status_code == 200


def test_list_genes(client):
    resp = client.get("/api/genes", params={"query": "CDK"})
    assert resp.status_code == 200
    body = resp.json()
    assert "CDK4" in body["genes"]


def test_gene_status(client):
    resp = client.get("/api/genes/CDK4/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["n_shrna_samples"] > 0
    assert body["pert_types"].get("trt_sh", 0) > 0


def test_signature_missing_returns_404(client):
    # 测试缓存目录是干净的
    resp = client.get("/api/genes/TOP2A/signature")
    assert resp.status_code == 404

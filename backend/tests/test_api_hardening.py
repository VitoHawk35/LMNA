#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L6：DELETE 缓存鉴权与 CORS 白名单（需要 LMNA_FIXTURE_DIR）。"""

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
    from fastapi.testclient import TestClient
    import main as main_module

    return TestClient(main_module.app)


@pytest.fixture()
def clean_task_files():
    import config

    def _clean():
        for name in os.listdir(config.TASK_CACHE_DIR):
            if name.endswith(".json"):
                os.remove(os.path.join(config.TASK_CACHE_DIR, name))

    _clean()
    yield
    _clean()


# ---------- 验收 1（接口层）：3 次 POST 同一基因只算 1 次 ----------

def test_api_three_compute_requests_share_one_task(
    client, monkeypatch, clean_task_files
):
    import task_queue

    calls = []

    def fake_worker(*args, **kwargs):
        calls.append(args)
        return {"ok": True}

    monkeypatch.setattr(task_queue, "_compute_task_worker", fake_worker)

    responses = [
        client.post("/api/genes/CDK4/compute", json={"method": "xsum"})
        for _ in range(3)
    ]
    assert all(r.status_code == 200 for r in responses)
    bodies = [r.json() for r in responses]
    assert len({b["task_id"] for b in bodies}) == 1
    assert [b["deduplicated"] for b in bodies] == [False, True, True]
    assert len(calls) == 1


def _no_token_env(monkeypatch):
    monkeypatch.delenv("LMNA_ADMIN_TOKEN", raising=False)
    import config
    monkeypatch.setattr(config, "LMNA_ADMIN_TOKEN", "")


# ---------- 验收 3：不带 token 返回 403 ----------

def test_delete_cache_without_token_returns_403(client, monkeypatch):
    _no_token_env(monkeypatch)
    resp = client.delete("/api/cache/CDK4")
    assert resp.status_code == 403


def test_delete_cache_unconfigured_token_forbids_even_with_header(
    client, monkeypatch
):
    _no_token_env(monkeypatch)
    resp = client.delete("/api/cache/CDK4", headers={"X-Admin-Token": "anything"})
    assert resp.status_code == 403


def test_delete_cache_wrong_token_returns_403(client, monkeypatch):
    monkeypatch.setenv("LMNA_ADMIN_TOKEN", "s3cret")
    resp = client.delete("/api/cache/CDK4", headers={"X-Admin-Token": "wrong"})
    assert resp.status_code == 403


def test_delete_cache_correct_token_allowed(client, monkeypatch):
    monkeypatch.setenv("LMNA_ADMIN_TOKEN", "s3cret")
    resp = client.delete("/api/cache/CDK4", headers={"X-Admin-Token": "s3cret"})
    assert resp.status_code == 200
    assert resp.json()["gene_name"] == "CDK4"


# ---------- CORS：逗号分隔；为空时不加中间件 ----------

def _cors_middleware(application):
    from fastapi.middleware.cors import CORSMiddleware

    return [m for m in application.user_middleware if m.cls is CORSMiddleware]


def test_cors_not_enabled_when_env_empty(monkeypatch):
    from fastapi import FastAPI
    import main as main_module

    monkeypatch.delenv("LMNA_CORS_ORIGINS", raising=False)
    monkeypatch.setattr(main_module.config, "LMNA_CORS_ORIGINS", "")

    test_app = FastAPI()
    origins = main_module.configure_cors(test_app)

    assert origins == []
    assert _cors_middleware(test_app) == []


def test_cors_parses_comma_separated_origins(monkeypatch):
    from fastapi import FastAPI
    import main as main_module

    monkeypatch.setenv(
        "LMNA_CORS_ORIGINS", "http://a.example, https://b.example ,"
    )

    test_app = FastAPI()
    origins = main_module.configure_cors(test_app)

    assert origins == ["http://a.example", "https://b.example"]
    middlewares = _cors_middleware(test_app)
    assert len(middlewares) == 1
    options = getattr(middlewares[0], "options", None) or middlewares[0].kwargs
    assert options["allow_origins"] == origins
    assert options["allow_credentials"] is True

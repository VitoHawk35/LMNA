#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L6：任务去重、心跳超时、启动清理。"""

import json
import os
from datetime import datetime, timedelta

import pytest

import config
import task_queue
from task_queue import TaskQueue, _dedup_identity


@pytest.fixture()
def clean_task_dir():
    """清空任务目录里的 JSON，保证每个测试互不影响。"""
    def _clean():
        for name in os.listdir(config.TASK_CACHE_DIR):
            if name.endswith(".json"):
                os.remove(os.path.join(config.TASK_CACHE_DIR, name))

    _clean()
    yield config.TASK_CACHE_DIR
    _clean()


@pytest.fixture()
def noop_worker(monkeypatch):
    """把 worker 换成不改变状态的空实现：任务会停在 pending，便于测去重。"""
    calls = []

    def fake_worker(
        gene_name, method, task_id, provider_type, score_mode="lof"
    ):
        calls.append((gene_name, method, task_id, provider_type, score_mode))
        return {"ok": True}

    monkeypatch.setattr(task_queue, "_compute_task_worker", fake_worker)
    return calls


def _read_task(task_dir, task_id):
    with open(os.path.join(task_dir, f"{task_id}.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def _write_task(task_dir, task_id, **overrides):
    data = {
        "task_id": task_id,
        "gene_name": "CDK4",
        "method": "xsum",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "message": "test",
    }
    data.update(overrides)
    with open(os.path.join(task_dir, f"{task_id}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- 验收 1：连续提交 3 次同一基因只算 1 次 ----------

def test_three_submits_same_gene_share_one_task(clean_task_dir, noop_worker):
    queue = TaskQueue()
    ids = [queue.submit("CDK4", "xsum") for _ in range(3)]

    assert ids[0] == ids[1] == ids[2]
    # worker 只被调用一次，任务文件只有一个
    assert len(noop_worker) == 1
    files = [n for n in os.listdir(clean_task_dir) if n.endswith(".json")]
    assert files == [f"{ids[0]}.json"]
    task = _read_task(clean_task_dir, ids[0])
    assert task["status"] == "pending"
    assert task["dedup_key"]


def test_submit_ex_reports_deduplicated(clean_task_dir, noop_worker):
    queue = TaskQueue()
    task_id, dedup = queue.submit_ex("CDK4", "xsum")
    assert dedup is False

    task_id_2, dedup_2 = queue.submit_ex("cdk4", "XSUM")
    assert task_id_2 == task_id
    assert dedup_2 is True


def test_concurrent_submits_create_only_one_task(clean_task_dir, noop_worker):
    from concurrent.futures import ThreadPoolExecutor

    queue = TaskQueue()
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: queue.submit("CDK4", "xsum"), range(8)))

    assert len(set(ids)) == 1
    assert len(noop_worker) == 1
    files = [n for n in os.listdir(clean_task_dir) if n.endswith(".json")]
    assert files == [f"{ids[0]}.json"]


def test_different_method_not_deduplicated(clean_task_dir, noop_worker):
    queue = TaskQueue()
    id_xsum = queue.submit("CDK4", "xsum")
    id_wtcs = queue.submit("CDK4", "wtcs")
    assert id_xsum != id_wtcs
    assert len(noop_worker) == 2


def test_param_change_breaks_dedup(clean_task_dir, noop_worker, monkeypatch):
    queue = TaskQueue()
    first = queue.submit("CDK4", "xsum")

    params = dict(task_queue.signature_params())
    params["FAST_MODE_TOP_N"] = 10
    monkeypatch.setattr(task_queue, "signature_params", lambda: params)

    second = queue.submit("CDK4", "xsum")
    assert first != second
    # 参数变化后 mode 也会从 full 变成 fast
    assert _read_task(clean_task_dir, second)["mode"] == "fast"


def test_completed_task_is_not_dedup_target(clean_task_dir, noop_worker):
    queue = TaskQueue()
    dedup_key, mode, params_hash = _dedup_identity("CDK4", "xsum")
    _write_task(
        clean_task_dir, "oldcompleted",
        status="completed", dedup_key=dedup_key, mode=mode, params_hash=params_hash,
    )

    new_id = queue.submit("CDK4", "xsum")
    assert new_id != "oldcompleted"


def test_expired_running_task_is_not_reused(clean_task_dir, noop_worker, monkeypatch):
    monkeypatch.setattr(config, "TASK_TIMEOUT_SEC", 7200)
    queue = TaskQueue()
    dedup_key, mode, params_hash = _dedup_identity("CDK4", "xsum")
    old = (datetime.now() - timedelta(hours=3)).isoformat()
    _write_task(
        clean_task_dir, "staletask", status="running",
        updated_at=old, dedup_key=dedup_key, mode=mode, params_hash=params_hash,
    )

    new_id = queue.submit("CDK4", "xsum")
    assert new_id != "staletask"
    # 旧任务被顺手标成 failed
    assert _read_task(clean_task_dir, "staletask")["status"] == "failed"


# ---------- 验收 2：running + 3 小时前 → failed ----------

def test_get_status_marks_three_hour_old_running_as_failed(
    clean_task_dir, monkeypatch
):
    monkeypatch.setattr(config, "TASK_TIMEOUT_SEC", 7200)
    old = (datetime.now() - timedelta(hours=3)).isoformat()
    _write_task(clean_task_dir, "timeout1", status="running", updated_at=old)

    status = TaskQueue().get_status("timeout1")

    assert status["status"] == "failed"
    assert "超时" in status["message"]
    # 落盘后再次查询仍是 failed（不会反复变）
    assert TaskQueue().get_status("timeout1")["status"] == "failed"


def test_get_status_keeps_recent_running(clean_task_dir, monkeypatch):
    monkeypatch.setattr(config, "TASK_TIMEOUT_SEC", 7200)
    recent = (datetime.now() - timedelta(minutes=5)).isoformat()
    _write_task(clean_task_dir, "alive", status="running", updated_at=recent)

    assert TaskQueue().get_status("alive")["status"] == "running"


def test_get_status_missing_returns_none(clean_task_dir):
    assert TaskQueue().get_status("does-not-exist") is None


def test_timeout_is_configurable(clean_task_dir, monkeypatch):
    monkeypatch.setattr(config, "TASK_TIMEOUT_SEC", 60)
    old = (datetime.now() - timedelta(minutes=5)).isoformat()
    _write_task(clean_task_dir, "shorttimeout", status="running", updated_at=old)

    assert TaskQueue().get_status("shorttimeout")["status"] == "failed"


# ---------- 启动清理 ----------

def test_startup_marks_pending_and_running_failed(clean_task_dir):
    _write_task(clean_task_dir, "p1", status="pending")
    _write_task(clean_task_dir, "r1", status="running")
    _write_task(clean_task_dir, "done1", status="completed")

    count = TaskQueue().mark_stale_tasks_on_startup()

    assert count == 2
    assert _read_task(clean_task_dir, "p1")["status"] == "failed"
    assert _read_task(clean_task_dir, "r1")["status"] == "failed"
    assert _read_task(clean_task_dir, "done1")["status"] == "completed"

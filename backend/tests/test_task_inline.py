#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LMNA_TASK_INLINE=1 时任务同进程执行。"""

import os

import task_queue
from task_queue import TaskQueue


def test_inline_submit_runs_worker_synchronously(monkeypatch):
    assert os.environ["LMNA_TASK_INLINE"] == "1"
    calls = []

    def fake_worker(gene_name, method, task_id, provider_type, score_mode="lof"):
        calls.append((gene_name, method, task_id, provider_type, score_mode))
        return {"ok": True}

    def fail_executor():
        raise AssertionError("inline 模式不应创建进程池")

    monkeypatch.setattr(task_queue, "_compute_task_worker", fake_worker)
    monkeypatch.setattr(task_queue, "_get_executor", fail_executor)

    task_id = TaskQueue().submit("CDK4", "xsum")

    assert len(calls) == 1
    assert calls[0][0] == "CDK4"
    assert calls[0][1] == "xsum"
    assert calls[0][2] == task_id
    assert calls[0][3] == os.environ["DATA_PROVIDER"]
    assert calls[0][4] == "lof"
    # submit 已同步返回，任务状态文件存在
    assert TaskQueue().get_status(task_id) is not None

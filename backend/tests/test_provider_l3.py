#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L6：L3Provider 空壳必须在创建/启动时给出清楚错误。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from l3_provider import L3Provider
from provider_factory import create_provider

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_create_provider_l3_raises_clear_error():
    with pytest.raises(NotImplementedError) as excinfo:
        create_provider("l3")
    message = str(excinfo.value)
    assert "L3Provider" in message
    assert "DATA_PROVIDER=l3" in message
    assert "L7e" in message


def test_l3_provider_shell_still_unimplemented():
    with pytest.raises(NotImplementedError):
        L3Provider()


def test_unknown_provider_message_mentions_options():
    with pytest.raises(ValueError) as excinfo:
        create_provider("nope")
    assert "l5" in str(excinfo.value)


def test_service_fails_at_startup_when_data_provider_l3():
    """DATA_PROVIDER=l3 时 import main 应立即失败，而不是等到任务执行。"""
    env = os.environ.copy()
    env["DATA_PROVIDER"] = "l3"
    # 避免测试环境变量影响：L3 在建 provider 之前就会失败
    result = subprocess.run(
        [sys.executable, "-c", "import main"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "L3Provider" in combined or "DATA_PROVIDER=l3" in combined

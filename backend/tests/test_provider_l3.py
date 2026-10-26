#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L7e 阶段 2：DATA_PROVIDER=l3 工厂行为（L3Provider 已实施，旧空壳测试作废）。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import composite_provider
from composite_provider import CompositeProvider
from provider_factory import create_provider

BACKEND_DIR = Path(__file__).resolve().parents[1]


class _FakeSide:
    """最小假 provider：只提供 CompositeProvider 启动校验所需的基因表。"""

    def __init__(self, symbols):
        self._symbols = list(symbols)

    def get_gene_symbols(self):
        return list(self._symbols)


def test_create_provider_l3_returns_composite(monkeypatch):
    monkeypatch.setattr(composite_provider, "L3Provider",
                        lambda: _FakeSide(["A", "B", "C"]))
    monkeypatch.setattr(composite_provider, "L5Provider",
                        lambda: _FakeSide(["A", "B", "C"]))
    provider = create_provider("l3")
    assert isinstance(provider, CompositeProvider)


def test_composite_refuses_mismatched_landmark_order(monkeypatch):
    monkeypatch.setattr(composite_provider, "L3Provider",
                        lambda: _FakeSide(["A", "B", "C"]))
    monkeypatch.setattr(composite_provider, "L5Provider",
                        lambda: _FakeSide(["A", "C", "B"]))
    with pytest.raises(RuntimeError) as excinfo:
        create_provider("l3")
    assert "landmark" in str(excinfo.value)


def test_unknown_provider_message_mentions_options():
    with pytest.raises(ValueError) as excinfo:
        create_provider("nope")
    assert "l5" in str(excinfo.value)


def test_service_fails_at_startup_when_l3_derived_missing():
    """DATA_PROVIDER=l3 但派生层缺失时 import main 应立即失败。"""
    env = os.environ.copy()
    env["DATA_PROVIDER"] = "l3"
    env["L3_DERIVED_DIR"] = str(BACKEND_DIR / "tests" / "data" / "no_such_dir")
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
    assert "L3" in combined

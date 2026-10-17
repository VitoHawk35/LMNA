#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据提供者工厂

把 provider 的选择逻辑集中到一处，避免 main.py / task_queue.py
各自硬编码 L5Provider。
"""

from data_provider import IDataProvider
from config import DATA_PROVIDER
from l5_provider import L5Provider
from l3_provider import L3Provider
from fixture_provider import FixtureProvider


def create_provider(kind: str = DATA_PROVIDER) -> IDataProvider:
    """
    根据配置创建数据提供者。

    Args:
        kind: "l5" | "l3" | "fixture"，默认取 config.DATA_PROVIDER

    Raises:
        ValueError: 未知的 provider 类型
    """
    normalized = (kind or "").strip().lower()
    if normalized == "l5":
        return L5Provider()
    if normalized == "l3":
        return L3Provider()
    if normalized == "fixture":
        return FixtureProvider()
    raise ValueError(
        f"未知的 DATA_PROVIDER: {kind!r}（可选值: l5 / l3 / fixture）"
    )

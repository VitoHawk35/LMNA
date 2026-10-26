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
        # L7e：L3 只覆盖签名侧（shRNA/ctl_vector 实例），药物打分仍走 L5，
        # 因此 DATA_PROVIDER=l3 返回组合提供者（签名=L3，药物=L5）。
        # L3 派生层缺失或花名册与 manifest 不一致时在启动阶段即报错。
        from composite_provider import CompositeProvider
        return CompositeProvider()
    if normalized == "fixture":
        return FixtureProvider()
    raise ValueError(
        f"未知的 DATA_PROVIDER: {kind!r}（可选值: l5 / l3 / fixture）"
    )

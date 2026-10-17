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
        # L3Provider 目前仍是空壳（见 l3_provider.py 与 L7e 方案）。
        # 这里显式失败，避免服务带病启动后在每个任务里才报错。
        raise NotImplementedError(
            "DATA_PROVIDER=l3 暂不可用：L3Provider 尚未实现。"
            " L3 数据源（Level 3 表达矩阵 + 按板 vehicle 重算 robust z-score）"
            "的实施见 docs/design/L7e-l3-provider.md；"
            "请把 DATA_PROVIDER 设为 l5（生产）或 fixture（测试）后重启服务。"
        )
    if normalized == "fixture":
        return FixtureProvider()
    raise ValueError(
        f"未知的 DATA_PROVIDER: {kind!r}（可选值: l5 / l3 / fixture）"
    )

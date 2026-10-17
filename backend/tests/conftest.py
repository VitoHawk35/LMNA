#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pytest 全局配置

必须在 import 任何后端模块之前设置环境变量，因为 config.py 在 import
时就读取 DATA_PROVIDER / LMNA_CACHE_DIR / BOOTSTRAP_N 等配置。

夹具目录由外部环境变量 LMNA_FIXTURE_DIR 提供；未提供时依赖夹具的测试
自行 skip（纯函数测试不受影响）。
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 会话级临时缓存目录（pytest 的 tmp_path_factory 在 conftest import 阶段
# 还不可用，因此这里先创建临时目录，进程退出时清理）。
_TEST_CACHE_DIR = tempfile.mkdtemp(prefix="lmna-test-cache-")
atexit.register(shutil.rmtree, _TEST_CACHE_DIR, ignore_errors=True)

# 这些环境变量必须在后端模块被 import 之前设置
os.environ["LMNA_CACHE_DIR"] = _TEST_CACHE_DIR
os.environ["DATA_PROVIDER"] = "fixture"
os.environ["LMNA_TASK_INLINE"] = "1"
os.environ["FAST_MODE_TOP_N"] = "0"
os.environ["BOOTSTRAP_N"] = "200"

FIXTURE_DIR_ENV = "LMNA_FIXTURE_DIR"


def fixture_available() -> bool:
    """夹具目录是否已设置且四个文件齐全。"""
    fixture_dir = os.getenv(FIXTURE_DIR_ENV)
    if not fixture_dir or not os.path.isdir(fixture_dir):
        return False
    required = (
        "lmna_fixture.npz",
        "lmna_fixture_sh.tsv",
        "lmna_fixture_cp.tsv",
        "lmna_fixture_meta.json",
    )
    return all(os.path.exists(os.path.join(fixture_dir, n)) for n in required)


def pytest_report_header(config):
    if fixture_available():
        return f"LMNA fixture: {os.getenv(FIXTURE_DIR_ENV)}"
    return "LMNA fixture: 未设置（依赖夹具的测试将 skip）"

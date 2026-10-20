#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pytest 全局配置

必须在 import 任何后端模块之前设置环境变量，因为 config.py 在 import
时就读取 DATA_PROVIDER / LMNA_CACHE_DIR / BOOTSTRAP_N 等配置。

夹具目录由外部环境变量 LMNA_FIXTURE_DIR 提供（指向 24MB 完整夹具时运行
完整回归）；未提供时默认回落到仓库内置的 mini 夹具
（backend/tests/data/mini_fixture/，D2，<=3MB），干净 clone 上
夹具相关测试也能开箱即跑。mini 缺失时依赖夹具的测试才 skip
（纯函数测试不受影响）。
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
# L4：生产默认 10000；常规测试用 200 控制耗时，验收测试在用例内显式传 M。
os.environ.setdefault("DRUG_NULL_N", "200")

FIXTURE_DIR_ENV = "LMNA_FIXTURE_DIR"

_FIXTURE_REQUIRED = (
    "lmna_fixture.npz",
    "lmna_fixture_sh.tsv",
    "lmna_fixture_cp.tsv",
    "lmna_fixture_meta.json",
)

# D2：仓库内置 mini 夹具（<=3MB）。未显式设置 LMNA_FIXTURE_DIR 时默认使用，
# 让干净 clone 上的夹具相关测试开箱即跑；显式设置后语义不变（指向谁就用谁）。
MINI_FIXTURE_DIR = Path(__file__).resolve().parent / "data" / "mini_fixture"


def _fixture_dir_complete(path) -> bool:
    return bool(
        path
        and os.path.isdir(path)
        and all(os.path.exists(os.path.join(path, n)) for n in _FIXTURE_REQUIRED)
    )


if not os.getenv(FIXTURE_DIR_ENV) and _fixture_dir_complete(MINI_FIXTURE_DIR):
    os.environ[FIXTURE_DIR_ENV] = str(MINI_FIXTURE_DIR)


def fixture_available() -> bool:
    """夹具目录是否已设置且四个文件齐全。"""
    return _fixture_dir_complete(os.getenv(FIXTURE_DIR_ENV))


def pytest_report_header(config):
    fixture_dir = os.getenv(FIXTURE_DIR_ENV)
    if fixture_available():
        tag = " (默认 mini)" if Path(fixture_dir) == MINI_FIXTURE_DIR else ""
        return f"LMNA fixture: {fixture_dir}{tag}"
    return "LMNA fixture: 未设置（依赖夹具的测试将 skip）"

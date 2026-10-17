#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缓存管理器
两层缓存：signature + drug_scores

缓存文件名带算法参数哈希（signature_params），参数/版本变化后不会读到旧结果。
所有 JSON 写入均为「临时文件 + os.replace」的原子写入，读取方不会看到半截 JSON。

药物缓存文件名同时编码两个正交维度：
- fast_mode：签名是否走快速模式（fast / normal）
- score_mode：筛药方向（lof / gof，L3）

文件名统一由 CacheManager.drug_scores_path() 构造，task_queue 等调用方不得各写一套。
"""

import glob
import hashlib
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from typing import Optional, Dict, Any

from config import SIGNATURE_CACHE_DIR, DRUG_SCORE_CACHE_DIR, signature_params

try:  # Linux / macOS
    import fcntl
except ImportError:  # Windows（本地开发/测试）：退回 msvcrt 文件锁
    fcntl = None


@contextmanager
def exclusive_file_lock(lock_path: str):
    """对 lock_path 加跨进程排他锁（Linux 用 fcntl.flock，Windows 用 msvcrt）。"""
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    with open(lock_path, "a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()

        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        else:
            import msvcrt

            lock_file.seek(0)
            while True:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


# 新文件名：{GENE}_{HASH}_signature.json
_SIGNATURE_RE = re.compile(r"^(.+)_([0-9a-f]{10})_signature\.json$")
_DRUG_SUFFIX = "_drug_scores.json"


def signature_params_hash(params: Optional[Dict[str, Any]] = None) -> str:
    """signature_params 的稳定短哈希（10 位），用于缓存文件名。"""
    if params is None:
        params = signature_params()
    payload = json.dumps(params, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]


def replace_file_with_retry(src: str, dst: str, attempts: int = 100, delay: float = 0.005):
    """os.replace 的原子替换；Windows 上目标被并发读取时短暂重试。"""
    last_error = None
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError as exc:  # Windows: 目标文件正被读取
            last_error = exc
            if i < attempts - 1:
                time.sleep(delay)
    raise last_error


def read_json_file(path: str) -> Optional[Dict[str, Any]]:
    """读取 JSON；兼容 Windows 上原子替换瞬间的短暂 PermissionError。"""
    for attempt in range(20):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except PermissionError:
            if attempt == 19:
                return None
            time.sleep(0.005)
        except json.JSONDecodeError:
            # 历史遗留的损坏文件：视为未缓存。
            return None
    return None


def atomic_write_json(path: str, data: Dict[str, Any]):
    """
    原子写入 JSON：先写 path + '.tmp.' + pid（再加随机后缀避免同进程多线程冲突），
    完整落盘后再 os.replace 覆盖目标文件。
    """
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp_path = f"{path}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
        replace_file_with_retry(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _normalize_fast_mode(fast_mode: Optional[str]) -> str:
    """归一化签名模式：fast / normal（兼容 L6 任务字段里的 full）。"""
    value = (fast_mode or "normal").strip().lower()
    if value == "fast":
        return "fast"
    # "normal"、"full"、空值都视为非快速模式。
    return "normal"


def _normalize_score_mode(score_mode: Optional[str]) -> str:
    """归一化筛药方向：lof / gof（L3）。"""
    return "gof" if (score_mode or "lof").strip().lower() == "gof" else "lof"


class CacheManager:
    """文件系统 JSON 缓存管理"""

    def __init__(self):
        os.makedirs(SIGNATURE_CACHE_DIR, exist_ok=True)
        os.makedirs(DRUG_SCORE_CACHE_DIR, exist_ok=True)

    # ---------------- 文件名（唯一构造入口） ----------------

    @staticmethod
    def signature_path(gene_name: str, params_hash: Optional[str] = None) -> str:
        h = params_hash or signature_params_hash()
        return os.path.join(
            SIGNATURE_CACHE_DIR, f"{gene_name.upper()}_{h}_signature.json"
        )

    @staticmethod
    def drug_scores_filename(
        gene_name: str,
        method: str,
        fast_mode: Optional[str] = "normal",
        score_mode: Optional[str] = "lof",
        params_hash: Optional[str] = None,
    ) -> str:
        """药物缓存文件名：{GENE}_{h}_{method}_{fast_mode}_{score_mode}_drug_scores.json"""
        h = params_hash or signature_params_hash()
        fast = _normalize_fast_mode(fast_mode)
        score = _normalize_score_mode(score_mode)
        return (
            f"{gene_name.upper()}_{h}_{(method or 'xsum').lower()}"
            f"_{fast}_{score}{_DRUG_SUFFIX}"
        )

    @classmethod
    def drug_scores_path(
        cls,
        gene_name: str,
        method: str,
        fast_mode: Optional[str] = "normal",
        score_mode: Optional[str] = "lof",
        params_hash: Optional[str] = None,
    ) -> str:
        return os.path.join(
            DRUG_SCORE_CACHE_DIR,
            cls.drug_scores_filename(
                gene_name, method,
                fast_mode=fast_mode, score_mode=score_mode,
                params_hash=params_hash,
            ),
        )

    # ---------------- Signature 缓存 ----------------

    def get_signature(self, gene_name: str) -> Optional[Dict[str, Any]]:
        return read_json_file(self.signature_path(gene_name))

    def save_signature(self, gene_name: str, data: Dict[str, Any]):
        atomic_write_json(self.signature_path(gene_name), data)

    def signature_exists(self, gene_name: str) -> bool:
        return os.path.exists(self.signature_path(gene_name))

    # ---------------- Drug Score 缓存 ----------------

    def _find_drug_scores_path(
        self,
        gene_name: str,
        method: str,
        fast_mode: Optional[str] = None,
        score_mode: Optional[str] = None,
    ) -> Optional[str]:
        """定位药物缓存。

        fast_mode / score_mode 为 None 时，在该维度上回退到同哈希下的任意值；
        回退排序固定为 fast_mode: normal > fast，score_mode: lof > gof，
        保证读取结果稳定。旧命名（无哈希）不参与查找，由 clear_gene 清理。
        """
        h = signature_params_hash()
        prefix = f"{gene_name.upper()}_{h}_{(method or 'xsum').lower()}_"
        pattern = os.path.join(
            DRUG_SCORE_CACHE_DIR, glob.escape(prefix) + "*" + _DRUG_SUFFIX
        )

        desired_fast = (
            None if fast_mode is None else _normalize_fast_mode(fast_mode)
        )
        desired_score = (
            None if score_mode is None else _normalize_score_mode(score_mode)
        )

        candidates = []
        for path in glob.glob(pattern):
            stem = os.path.basename(path)[len(prefix):-len(_DRUG_SUFFIX)]
            parts = stem.rsplit("_", 1)
            if len(parts) != 2:
                continue
            fm, sm = parts
            if desired_fast is not None and fm != desired_fast:
                continue
            if desired_score is not None and sm != desired_score:
                continue
            candidates.append((fm, sm, path))

        if not candidates:
            return None

        if desired_fast is not None and desired_score is not None:
            exact = self.drug_scores_path(
                gene_name, method,
                fast_mode=desired_fast, score_mode=desired_score,
            )
            if os.path.exists(exact):
                return exact

        def _preference(item):
            fm, sm, path = item
            fast_rank = {"normal": 0, "fast": 1}.get(fm, 2)
            score_rank = {"lof": 0, "gof": 1}.get(sm, 2)
            return (
                0 if desired_fast is not None else fast_rank,
                0 if desired_score is not None else score_rank,
                path,
            )

        return min(candidates, key=_preference)[2]

    def get_drug_scores(
        self,
        gene_name: str,
        method: str,
        mode: str = "lof",
        fast_mode: Optional[str] = None,
        score_mode: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """读取药物缓存。

        `mode` 是 L3 既有调用方使用的 score_mode 别名（lof/gof），保持 API 兼容；
        新调用方可以显式传 fast_mode / score_mode。
        """
        resolved_score = score_mode if score_mode is not None else mode
        path = self._find_drug_scores_path(
            gene_name, method,
            fast_mode=fast_mode, score_mode=resolved_score,
        )
        if path is None:
            return None
        return read_json_file(path)

    def save_drug_scores(
        self,
        gene_name: str,
        method: str,
        data: Dict[str, Any],
        mode: str = "lof",
        fast_mode: str = "normal",
        score_mode: Optional[str] = None,
    ):
        """写入药物缓存；`mode` 为 score_mode 的兼容别名。"""
        resolved_score = score_mode if score_mode is not None else mode
        path = self.drug_scores_path(
            gene_name, method,
            fast_mode=fast_mode, score_mode=resolved_score,
        )
        atomic_write_json(path, data)

    def drug_scores_exist(
        self,
        gene_name: str,
        method: str,
        mode: str = "lof",
        fast_mode: Optional[str] = None,
        score_mode: Optional[str] = None,
    ) -> bool:
        resolved_score = score_mode if score_mode is not None else mode
        return self._find_drug_scores_path(
            gene_name, method,
            fast_mode=fast_mode, score_mode=resolved_score,
        ) is not None

    # ---------------- 通用清理 ----------------

    def clear_gene(self, gene_name: str) -> bool:
        """用 glob 清除某基因的所有缓存版本（含旧命名与残留临时文件）。"""
        gene_upper = gene_name.upper()
        escaped = glob.escape(gene_upper)
        patterns = [
            # 新命名 + 旧命名
            os.path.join(SIGNATURE_CACHE_DIR, f"{escaped}_*_signature.json"),
            os.path.join(SIGNATURE_CACHE_DIR, f"{escaped}_signature.json"),
            # 新命名（含 fast_mode/score_mode）与旧命名（仅有 method 或 method_mode）
            os.path.join(DRUG_SCORE_CACHE_DIR, f"{escaped}_*_drug_scores.json"),
            # 写入中途残留的临时文件
            os.path.join(SIGNATURE_CACHE_DIR, f"{escaped}_*_signature.json.tmp.*"),
            os.path.join(
                DRUG_SCORE_CACHE_DIR, f"{escaped}_*_drug_scores.json.tmp.*"
            ),
        ]
        deleted = False
        for pattern in patterns:
            for path in glob.glob(pattern):
                try:
                    os.remove(path)
                    deleted = True
                except FileNotFoundError:
                    pass
        return deleted

    def list_cached_genes(self) -> list:
        """列出所有已缓存 signature 的基因（解析新文件名并去重）。"""
        genes = set()
        for f in os.listdir(SIGNATURE_CACHE_DIR):
            match = _SIGNATURE_RE.match(f)
            if match:
                genes.add(match.group(1))
        return sorted(genes)

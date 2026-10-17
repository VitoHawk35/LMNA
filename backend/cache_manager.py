#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缓存管理器
两层缓存：signature + drug_scores

缓存文件名带算法参数哈希（signature_params），参数/版本变化后不会读到旧结果。
所有 JSON 写入均为「临时文件 + os.replace」的原子写入，读取方不会看到半截 JSON。
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


# 新文件名：{GENE}_{HASH}_signature.json / {GENE}_{HASH}_{METHOD}_{MODE}_drug_scores.json
_SIGNATURE_RE = re.compile(r"^(.+)_([0-9a-f]{10})_signature\.json$")


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


class CacheManager:
    """文件系统 JSON 缓存管理"""

    def __init__(self):
        os.makedirs(SIGNATURE_CACHE_DIR, exist_ok=True)
        os.makedirs(DRUG_SCORE_CACHE_DIR, exist_ok=True)

    # ---------------- 文件名 ----------------

    @staticmethod
    def signature_path(gene_name: str, params_hash: Optional[str] = None) -> str:
        h = params_hash or signature_params_hash()
        return os.path.join(
            SIGNATURE_CACHE_DIR, f"{gene_name.upper()}_{h}_signature.json"
        )

    @staticmethod
    def drug_scores_path(
        gene_name: str,
        method: str,
        mode: str = "normal",
        params_hash: Optional[str] = None,
    ) -> str:
        h = params_hash or signature_params_hash()
        return os.path.join(
            DRUG_SCORE_CACHE_DIR,
            f"{gene_name.upper()}_{h}_{method.lower()}_{(mode or 'normal').lower()}"
            f"_drug_scores.json",
        )

    # ---------------- Signature 缓存 ----------------

    def get_signature(self, gene_name: str) -> Optional[Dict[str, Any]]:
        return read_json_file(self.signature_path(gene_name))

    def save_signature(self, gene_name: str, data: Dict[str, Any]):
        atomic_write_json(self.signature_path(gene_name), data)

    def signature_exists(self, gene_name: str) -> bool:
        return os.path.exists(self.signature_path(gene_name))

    # ---------------- Drug Score 缓存 ----------------

    @staticmethod
    def _hash_prefix(gene_name: str, params_hash: Optional[str] = None) -> str:
        h = params_hash or signature_params_hash()
        return f"{gene_name.upper()}_{h}_"

    def _find_drug_scores_path(
        self, gene_name: str, method: str, mode: Optional[str] = "normal"
    ) -> Optional[str]:
        """定位药物缓存：优先当前 mode；未指定/缺失时回退到同哈希的任一 mode。"""
        if mode is not None:
            exact = self.drug_scores_path(gene_name, method, mode)
            if os.path.exists(exact):
                return exact

        prefix = self._hash_prefix(gene_name)
        pattern = os.path.join(
            DRUG_SCORE_CACHE_DIR,
            f"{glob.escape(prefix)}{method.lower()}_*_drug_scores.json",
        )
        candidates = sorted(glob.glob(pattern))
        if not candidates:
            return None
        if mode is not None:
            preferred = [
                p for p in candidates
                if p.endswith(f"_{mode.lower()}_drug_scores.json")
            ]
            if preferred:
                return preferred[0]
        # 回退时优先 normal，保证输出稳定。
        normal = [p for p in candidates if p.endswith("_normal_drug_scores.json")]
        return (normal or candidates)[0]

    def get_drug_scores(
        self, gene_name: str, method: str, mode: Optional[str] = "normal"
    ) -> Optional[Dict[str, Any]]:
        path = self._find_drug_scores_path(gene_name, method, mode)
        if path is None:
            return None
        return read_json_file(path)

    def save_drug_scores(
        self,
        gene_name: str,
        method: str,
        data: Dict[str, Any],
        mode: str = "normal",
    ):
        atomic_write_json(self.drug_scores_path(gene_name, method, mode), data)

    def drug_scores_exist(
        self, gene_name: str, method: str, mode: Optional[str] = "normal"
    ) -> bool:
        return self._find_drug_scores_path(gene_name, method, mode) is not None

    # ---------------- 通用清理 ----------------

    def clear_gene(self, gene_name: str) -> bool:
        """用 glob 清除某基因的所有缓存版本（含旧命名与残留临时文件）。"""
        gene_upper = gene_name.upper()
        patterns = [
            # 新命名 + 旧命名
            os.path.join(SIGNATURE_CACHE_DIR, f"{gene_upper}_*_signature.json"),
            os.path.join(SIGNATURE_CACHE_DIR, f"{gene_upper}_signature.json"),
            # 新命名 {hash}_{method}_{mode} 与旧命名 {method}
            os.path.join(DRUG_SCORE_CACHE_DIR, f"{gene_upper}_*_drug_scores.json"),
            # 写入中途残留的临时文件
            os.path.join(SIGNATURE_CACHE_DIR, f"{gene_upper}_*_signature.json.tmp.*"),
            os.path.join(
                DRUG_SCORE_CACHE_DIR, f"{gene_upper}_*_drug_scores.json.tmp.*"
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

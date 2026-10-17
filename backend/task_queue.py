#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
轻量级异步任务队列
基于 ProcessPoolExecutor + JSON 状态文件
"""

import os
import json
import time
import uuid
import hashlib
import threading
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Optional, Tuple
from datetime import datetime

import config
from config import TASK_CACHE_DIR, DATA_PROVIDER, signature_params
from cache_manager import CacheManager, atomic_write_json, read_json_file
from signature_engine import SignatureEngine
from drug_scorer import DrugScorer
from provider_factory import create_provider


# 全局进程池（延迟初始化）
_executor: Optional[ProcessPoolExecutor] = None

_ACTIVE_STATUSES = ("pending", "running")
_TIMEOUT_MESSAGE = "任务超时或服务重启"

# 同进程内串行化“查重 + 落盘”，避免多线程同时提交同一基因时都查不到对方。
# 生产按 D6 使用 gunicorn -w 1 --threads 8，单进程内即可完全覆盖竞态。
_submit_lock = threading.Lock()


def _timeout_seconds() -> int:
    """当前任务超时阈值（秒）。

    通过 config 模块属性读取，测试可以用 monkeypatch 覆盖；
    也支持运行期直接改环境变量后重新读取 config。
    """
    return int(getattr(config, "TASK_TIMEOUT_SEC", 7200))


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _is_expired(updated_at: Optional[str], timeout_sec: int) -> bool:
    """updated_at 距现在是否已超过 timeout_sec 秒（解析失败按未超时处理）。"""
    stamp = _parse_iso(updated_at)
    if stamp is None:
        return False
    try:
        return (datetime.now() - stamp).total_seconds() > timeout_sec
    except (TypeError, OverflowError):
        return False


def _dedup_identity(gene_name: str, method: str) -> Tuple[str, str, str]:
    """生成任务去重标识。

    Returns:
        (dedup_key, mode, params_hash)
        - gene/method 归一化后参与 key
        - mode 目前由 FAST_MODE_TOP_N 推导（fast/full）
        - params_hash 覆盖签名计算参数，参数变化后不再命中旧任务
    """
    gene = (gene_name or "").strip().upper()
    method_norm = (method or "").strip().lower()
    params = signature_params()
    mode = "fast" if int(params.get("FAST_MODE_TOP_N", 0) or 0) > 0 else "full"
    payload = {"gene": gene, "method": method_norm, "mode": mode, "params": params}
    params_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    dedup_key = hashlib.sha256(
        f"{gene}|{method_norm}|{mode}|{params_hash}".encode("utf-8")
    ).hexdigest()[:32]
    return dedup_key, mode, params_hash


def _get_executor() -> ProcessPoolExecutor:
    global _executor
    if _executor is None:
        # 使用最多 2 个 worker 避免内存爆炸
        _executor = ProcessPoolExecutor(max_workers=2)
    return _executor


def _build_provider(provider_type: str):
    """在 worker 进程中构建数据提供者"""
    return create_provider(provider_type)


def _compute_task_worker(
    gene_name: str,
    method: str,
    task_id: str,
    provider_type: str
) -> Dict:
    """
    在子进程中执行的计算任务。
    """
    try:
        # 更新状态为 running
        _update_task_status(task_id, "running", message="开始计算签名...")

        cache = CacheManager()
        provider = _build_provider(provider_type)

        # 1. 检查 signature 缓存
        sig_data = cache.get_signature(gene_name)
        if sig_data is None:
            engine = SignatureEngine(provider)
            sig_data = engine.compute_signature(gene_name)
            cache.save_signature(gene_name, sig_data)
            _update_task_status(task_id, "running", message="签名计算完成，开始筛药...")
        else:
            _update_task_status(task_id, "running", message="使用缓存签名，开始筛药...")

        # 2. 检查 drug score 缓存
        _update_task_status(task_id, "running", message="开始筛药...")
        # 药物结果依赖签名模式（快速模式签名 vs 统计筛选签名），写进缓存文件名。
        mode = "fast" if sig_data.get("fast_mode") else "normal"
        drug_data = cache.get_drug_scores(gene_name, method)
        if drug_data is None:
            scorer = DrugScorer(provider)
            drug_data = scorer.score_drugs(sig_data, method=method)
            cache.save_drug_scores(gene_name, method, drug_data, mode=mode)
        _update_task_status(task_id, "running", message="筛药完成，正在组装结果...")

        # 3. 组装结果
        result = {
            "signature": {
                "gene_name": sig_data["gene_name"],
                "n_samples": sig_data["n_samples"],
                "n_sig": sig_data.get(
                    "n_sig",
                    len(sig_data["up_genes"]) + len(sig_data["down_genes"]),
                ),
                "n_up_genes": len(sig_data["up_genes"]),
                "n_down_genes": len(sig_data["down_genes"]),
                "up_genes": sig_data["up_genes"],
                "down_genes": sig_data["down_genes"],
                "fast_mode": sig_data.get("fast_mode", False),
                "params": sig_data.get("params", {}),
            },
            "drug_results": {
                "method": drug_data["method"],
                "top_drugs": drug_data["top_drugs"],
                "bottom_drugs": drug_data["bottom_drugs"],
            }
        }

        _update_task_status(
            task_id, "completed",
            result=result,
            message="计算完成"
        )
        return result

    except Exception as e:
        _update_task_status(
            task_id, "failed",
            error=str(e),
            message=f"计算失败: {str(e)}"
        )
        raise


def _update_task_status(
    task_id: str,
    status: str,
    result: Optional[Dict] = None,
    error: Optional[str] = None,
    message: str = ""
):
    """更新任务状态文件"""
    path = os.path.join(TASK_CACHE_DIR, f"{task_id}.json")
    data = read_json_file(path) or {}

    data["status"] = status
    data["updated_at"] = datetime.now().isoformat()
    if message:
        data["message"] = message
    if result is not None:
        data["result"] = result
    if error is not None:
        data["error"] = error

    atomic_write_json(path, data)


class TaskQueue:
    """
    任务队列管理器
    """

    def __init__(self):
        self.cache = CacheManager()

    def _find_active_task(self, dedup_key: str) -> Optional[str]:
        """查找相同去重键且仍处于 pending/running 的任务。

        已超时的 running 任务视为失效：顺手标为 failed 后跳过，
        避免把新提交去重到一个实际已死掉的任务上。
        """
        if not dedup_key or not os.path.isdir(TASK_CACHE_DIR):
            return None
        timeout_sec = _timeout_seconds()
        try:
            names = os.listdir(TASK_CACHE_DIR)
        except OSError:
            return None
        for name in names:
            if not name.endswith(".json"):
                continue
            path = os.path.join(TASK_CACHE_DIR, name)
            data = read_json_file(path)
            if data is None:
                continue
            if data.get("status") not in _ACTIVE_STATUSES:
                continue
            if data.get("dedup_key") != dedup_key:
                continue
            if data.get("status") == "running" and _is_expired(
                data.get("updated_at"), timeout_sec
            ):
                task_id = data.get("task_id") or name[:-5]
                _update_task_status(
                    task_id, "failed",
                    error=_TIMEOUT_MESSAGE,
                    message=_TIMEOUT_MESSAGE,
                )
                continue
            return data.get("task_id") or name[:-5]
        return None

    def submit(self, gene_name: str, method: str = "xsum") -> str:
        """
        提交计算任务。

        Returns:
            task_id
        """
        task_id, _ = self.submit_ex(gene_name, method)
        return task_id

    def submit_ex(self, gene_name: str, method: str = "xsum") -> Tuple[str, bool]:
        """提交计算任务，并返回是否命中了已有任务（去重）。

        Returns:
            (task_id, deduplicated)
        """
        gene = (gene_name or "").strip().upper()
        method_norm = (method or "").strip().lower()
        dedup_key, mode, params_hash = _dedup_identity(gene, method_norm)

        with _submit_lock:
            existing = self._find_active_task(dedup_key)
            if existing is not None:
                return existing, True

            task_id = str(uuid.uuid4())[:16]
            task_path = os.path.join(TASK_CACHE_DIR, f"{task_id}.json")

            # 写入初始状态（原子写入；dedup_key/mode/params_hash 为新增字段，老任务没有）
            atomic_write_json(task_path, {
                "task_id": task_id,
                "gene_name": gene,
                "method": method_norm,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "message": "任务已提交，等待执行...",
                "mode": mode,
                "params_hash": params_hash,
                "dedup_key": dedup_key,
            })

        # LMNA_TASK_INLINE=1 时同进程同步执行（测试用），否则提交到进程池
        if os.getenv("LMNA_TASK_INLINE") == "1":
            try:
                _compute_task_worker(
                    gene,
                    method_norm,
                    task_id,
                    DATA_PROVIDER
                )
            except Exception:
                # worker 已把失败状态写入任务文件，这里不再向调用方抛异常，
                # 保持与进程池模式一致的“提交即返回”语义。
                pass
        else:
            executor = _get_executor()
            executor.submit(
                _compute_task_worker,
                gene,
                method_norm,
                task_id,
                DATA_PROVIDER
            )

        return task_id, False

    def get_status(self, task_id: str) -> Optional[Dict]:
        """查询任务状态；running 且心跳超时的任务会就地标为 failed。"""
        path = os.path.join(TASK_CACHE_DIR, f"{task_id}.json")
        data = read_json_file(path)
        if data is None:
            return None

        if data.get("status") == "running" and _is_expired(
            data.get("updated_at"), _timeout_seconds()
        ):
            _update_task_status(
                task_id, "failed",
                error=_TIMEOUT_MESSAGE,
                message=_TIMEOUT_MESSAGE,
            )
            data = read_json_file(path)
        return data

    def mark_stale_tasks_on_startup(self) -> int:
        """服务启动时把残留的 pending/running 任务标为 failed。

        进程池里的任务随进程消失，若不清理会永远停在 pending/running。

        Returns:
            被标记的任务数量。
        """
        count = 0
        if not os.path.isdir(TASK_CACHE_DIR):
            return count
        for name in os.listdir(TASK_CACHE_DIR):
            if not name.endswith(".json"):
                continue
            path = os.path.join(TASK_CACHE_DIR, name)
            data = read_json_file(path)
            if data is None:
                continue
            if data.get("status") not in _ACTIVE_STATUSES:
                continue
            _update_task_status(
                data.get("task_id") or name[:-5], "failed",
                error=_TIMEOUT_MESSAGE,
                message="服务重启，任务已中断",
            )
            count += 1
        return count

    def list_tasks(self, limit: int = 50) -> list:
        """列出最近的任务"""
        tasks = []
        for f in sorted(
            os.listdir(TASK_CACHE_DIR),
            key=lambda x: os.path.getmtime(os.path.join(TASK_CACHE_DIR, x)),
            reverse=True
        )[:limit]:
            if f.endswith('.json'):
                data = read_json_file(os.path.join(TASK_CACHE_DIR, f))
                if data is not None:
                    tasks.append(data)
        return tasks

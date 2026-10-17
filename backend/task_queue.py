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
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Optional
from datetime import datetime

from config import TASK_CACHE_DIR, DATA_PROVIDER
from cache_manager import CacheManager
from signature_engine import SignatureEngine
from drug_scorer import DrugScorer
from provider_factory import create_provider


# 全局进程池（延迟初始化）
_executor: Optional[ProcessPoolExecutor] = None


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
        drug_data = cache.get_drug_scores(gene_name, method)
        if drug_data is None:
            scorer = DrugScorer(provider)
            drug_data = scorer.score_drugs(sig_data, method=method)
            cache.save_drug_scores(gene_name, method, drug_data)

        # 3. 组装结果
        result = {
            "signature": {
                "gene_name": sig_data["gene_name"],
                "n_samples": sig_data["n_samples"],
                "n_up_genes": len(sig_data["up_genes"]),
                "n_down_genes": len(sig_data["down_genes"]),
                "up_genes": sig_data["up_genes"],
                "down_genes": sig_data["down_genes"],
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
    data = {}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

    data["status"] = status
    data["updated_at"] = datetime.now().isoformat()
    if message:
        data["message"] = message
    if result is not None:
        data["result"] = result
    if error is not None:
        data["error"] = error

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class TaskQueue:
    """
    任务队列管理器
    """

    def __init__(self):
        self.cache = CacheManager()

    def submit(self, gene_name: str, method: str = "xsum") -> str:
        """
        提交计算任务。

        Returns:
            task_id
        """
        task_id = str(uuid.uuid4())[:16]
        task_path = os.path.join(TASK_CACHE_DIR, f"{task_id}.json")

        # 写入初始状态
        with open(task_path, 'w', encoding='utf-8') as f:
            json.dump({
                "task_id": task_id,
                "gene_name": gene_name.upper(),
                "method": method.lower(),
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "message": "任务已提交，等待执行..."
            }, f, ensure_ascii=False, indent=2)

        # LMNA_TASK_INLINE=1 时同进程同步执行（测试用），否则提交到进程池
        if os.getenv("LMNA_TASK_INLINE") == "1":
            try:
                _compute_task_worker(
                    gene_name,
                    method,
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
                gene_name,
                method,
                task_id,
                DATA_PROVIDER
            )

        return task_id

    def get_status(self, task_id: str) -> Optional[Dict]:
        """查询任务状态"""
        path = os.path.join(TASK_CACHE_DIR, f"{task_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def list_tasks(self, limit: int = 50) -> list:
        """列出最近的任务"""
        tasks = []
        for f in sorted(
            os.listdir(TASK_CACHE_DIR),
            key=lambda x: os.path.getmtime(os.path.join(TASK_CACHE_DIR, x)),
            reverse=True
        )[:limit]:
            if f.endswith('.json'):
                with open(os.path.join(TASK_CACHE_DIR, f), 'r', encoding='utf-8') as fp:
                    tasks.append(json.load(fp))
        return tasks

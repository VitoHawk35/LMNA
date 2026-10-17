#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LMNA 基因特征系统 FastAPI 入口
"""

import os
import secrets
import sys

# 将 backend 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Literal

import config
from config import (
    API_HOST, API_PORT, DEFAULT_TOP_K, DEFAULT_BOTTOM_K, DATA_PROVIDER
)
from provider_factory import create_provider
from cache_manager import CacheManager
from task_queue import TaskQueue

app = FastAPI(
    title="LMNA Gene Signature & Drug Screening System",
    description="基于 LINCS L1000 的基因敲低特征定义与药物筛选平台",
    version="1.0.0"
)

def cors_origins() -> List[str]:
    """读取 LMNA_CORS_ORIGINS（逗号分隔）；为空表示同源部署，不启用 CORS。"""
    raw = os.getenv("LMNA_CORS_ORIGINS", config.LMNA_CORS_ORIGINS or "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def configure_cors(target_app: FastAPI) -> List[str]:
    """按环境变量配置 CORS；返回实际生效的来源列表。

    D2：同源部署（nginx 反代 /api）时允许为空，此时不添加中间件，
    避免 allow_origins=["*"] + allow_credentials=True 的不合规组合。
    """
    origins = cors_origins()
    if origins:
        target_app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    return origins


configure_cors(app)

# 全局单例
_provider = create_provider()
_cache = CacheManager()
_queue = TaskQueue()


@app.on_event("startup")
def _mark_stale_tasks_on_startup():
    """启动时清理上次进程残留的 pending/running 任务。"""
    _queue.mark_stale_tasks_on_startup()


# ============ 请求/响应模型 ============

class ComputeRequest(BaseModel):
    method: str = "xsum"  # "xsum" or "wtcs"
    mode: Literal["lof", "gof"] = "lof"  # lof=找逆转药（top 降序）；gof=找模拟药（top 升序）


class DrugQueryRequest(BaseModel):
    method: str = "xsum"
    mode: Literal["lof", "gof"] = "lof"
    include_red: bool = False
    top_n: int = DEFAULT_TOP_K
    bottom_n: int = DEFAULT_BOTTOM_K


# ============ 路由 ============

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "provider": DATA_PROVIDER,
        "available_genes": len(_provider.list_available_genes()),
        "cached_signatures": len(_cache.list_cached_genes()),
    }


@app.get("/api/genes")
def list_genes(query: Optional[str] = None):
    """列出所有有 shRNA 数据的基因，支持前缀搜索"""
    genes = _provider.list_available_genes()
    if query:
        q = query.strip().upper()
        genes = [g for g in genes if g.startswith(q)]
    return {"genes": genes[:500], "total": len(genes)}


@app.get("/api/genes/{gene_name}/status")
def gene_status(gene_name: str):
    """检查某基因的 shRNA 数据可用性"""
    df = _provider.get_shrna_samples(gene_name)
    n = len(df)
    available = n >= config.MIN_SH_SAMPLES
    return {
        "gene_name": gene_name.upper(),
        "available": available,
        "n_shrna_samples": n,
        "pert_types": df["pert_type"].value_counts().to_dict() if n > 0 else {},
        "cached": _cache.signature_exists(gene_name),
    }


@app.get("/api/genes/{gene_name}/suitability")
def gene_suitability(gene_name: str):
    """
    基因适用性预检（L3）。

    只做数据前置检查（不计算签名，几秒内返回）；若该基因已有缓存签名，
    则一并返回签名里的 qc（判档结果）。
    """
    from suitability import precheck

    pre = precheck(_provider, gene_name)
    sig = _cache.get_signature(gene_name)
    qc = sig.get("qc") if sig else None
    return {
        "gene_name": gene_name.upper(),
        "precheck": pre,
        "qc": qc,
        "grade": qc.get("grade") if qc else None,
        "cached_signature": sig is not None,
    }


@app.post("/api/genes/{gene_name}/compute")
def compute_gene(gene_name: str, req: ComputeRequest):
    """提交某基因的 signature 计算任务"""
    # 先检查可用性
    df = _provider.get_shrna_samples(gene_name)
    n_samples = len(df)
    if n_samples == 0:
        raise HTTPException(
            status_code=404,
            detail=f"基因 {gene_name} 没有 shRNA 敲低数据"
        )

    # L3 数据门槛：独立 hairpin < 2 时无法排除 shRNA 脱靶
    n_hairpins = (
        int(df["pert_id"].nunique()) if "pert_id" in df.columns else n_samples
    )
    if n_hairpins < config.SUITABILITY_MIN_HAIRPINS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"基因 {gene_name} 的独立 shRNA hairpin 数不足："
                f"当前 {n_hairpins} 个，至少需要 "
                f"{config.SUITABILITY_MIN_HAIRPINS} 个；"
                "少于 2 个无法排除 shRNA 脱靶"
            )
        )

    if n_samples < config.MIN_SH_SAMPLES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"基因 {gene_name} 的 shRNA 样本数不足："
                f"当前 {n_samples} 个，至少需要 {config.MIN_SH_SAMPLES} 个"
            )
        )

    method = req.method.lower()
    if method not in ("xsum", "wtcs"):
        raise HTTPException(status_code=400, detail="method 必须是 xsum 或 wtcs")

    task_id, deduplicated = _queue.submit_ex(
        gene_name, method, score_mode=req.mode
    )
    task = _queue.get_status(task_id) or {}
    return {
        "task_id": task_id,
        "gene_name": gene_name.upper(),
        "method": method,
        "mode": req.mode,
        "status": task.get("status", "pending"),
        # L6 字段：本次提交是否复用了已有的 pending/running 任务
        "deduplicated": deduplicated,
    }


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    """查询任务状态"""
    status = _queue.get_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return status


@app.get("/api/tasks")
def list_tasks(limit: int = 20):
    """列出最近任务"""
    return {"tasks": _queue.list_tasks(limit)}


@app.get("/api/genes/{gene_name}/signature")
def get_signature(gene_name: str):
    """获取某基因的 signature 基因列表"""
    sig = _cache.get_signature(gene_name)
    if sig is None:
        raise HTTPException(
            status_code=404,
            detail=f"基因 {gene_name} 的签名尚未计算，请先提交计算任务"
        )
    return {
        "gene_name": sig["gene_name"],
        "n_samples": sig["n_samples"],
        "n_sig": sig.get("n_sig", len(sig["up_genes"]) + len(sig["down_genes"])),
        "n_up_genes": len(sig["up_genes"]),
        "n_down_genes": len(sig["down_genes"]),
        "up_genes": sig["up_genes"],
        "down_genes": sig["down_genes"],
        "bootstrap_n": sig.get("bootstrap_n", 0),
        "fast_mode": sig.get("fast_mode", False),
        "params": sig.get("params", {}),
        # L3 适用性判档（旧缓存没有 qc 时返回 None）
        "qc": sig.get("qc"),
        "n_hairpins": sig.get("n_hairpins"),
        "n_cells": sig.get("n_cells"),
    }


@app.get("/api/genes/{gene_name}/drugs")
def get_drugs(
    gene_name: str,
    method: str = "xsum",
    mode: Literal["lof", "gof"] = "lof",
    include_red: bool = False,
    top_n: int = DEFAULT_TOP_K,
    bottom_n: int = DEFAULT_BOTTOM_K
):
    """获取某基因的筛药结果（L3：红档默认屏蔽药物列表）。"""
    drug_data = _cache.get_drug_scores(gene_name, method, mode=mode)
    if drug_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"基因 {gene_name} 的 {method}（{mode}）筛药结果尚未计算"
        )

    sig = _cache.get_signature(gene_name)
    qc = sig.get("qc") if sig else None
    suppress_red = bool(
        qc and qc.get("grade") == "red" and not include_red
    )

    return {
        "gene_name": drug_data["gene_name"],
        "method": drug_data["method"],
        "mode": drug_data.get("mode", mode),
        "n_up_genes": drug_data["n_up_genes"],
        "n_down_genes": drug_data["n_down_genes"],
        "top_drugs": [] if suppress_red else drug_data["top_drugs"][:top_n],
        "bottom_drugs": [] if suppress_red else drug_data["bottom_drugs"][:bottom_n],
        "qc": qc,
        "include_red": include_red,
        "red_suppressed": suppress_red,
    }


@app.delete("/api/cache/{gene_name}")
def clear_cache(
    gene_name: str,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
):
    """清除某基因的缓存（需要 X-Admin-Token 管理令牌）。"""
    expected = os.getenv("LMNA_ADMIN_TOKEN", "") or config.LMNA_ADMIN_TOKEN or ""
    if not expected:
        # 未配置令牌时禁用该危险接口，避免默认无保护
        raise HTTPException(
            status_code=403,
            detail="缓存删除接口未启用：管理员未设置 LMNA_ADMIN_TOKEN",
        )
    provided = x_admin_token or ""
    if not provided or not secrets.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=403, detail="管理员令牌无效")

    deleted = _cache.clear_gene(gene_name)
    return {
        "gene_name": gene_name.upper(),
        "deleted": deleted,
        "message": "缓存已清除" if deleted else "该基因无缓存"
    }


# ============ 启动 ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=False)

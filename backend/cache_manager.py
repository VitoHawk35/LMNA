#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缓存管理器
两层缓存：signature + drug_scores
"""

import os
import json
from typing import Optional, Dict, Any

from config import SIGNATURE_CACHE_DIR, DRUG_SCORE_CACHE_DIR


class CacheManager:
    """文件系统 JSON 缓存管理"""

    def __init__(self):
        os.makedirs(SIGNATURE_CACHE_DIR, exist_ok=True)
        os.makedirs(DRUG_SCORE_CACHE_DIR, exist_ok=True)

    # ---------------- Signature 缓存 ----------------

    def get_signature(self, gene_name: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(SIGNATURE_CACHE_DIR, f"{gene_name.upper()}_signature.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def save_signature(self, gene_name: str, data: Dict[str, Any]):
        path = os.path.join(SIGNATURE_CACHE_DIR, f"{gene_name.upper()}_signature.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def signature_exists(self, gene_name: str) -> bool:
        path = os.path.join(SIGNATURE_CACHE_DIR, f"{gene_name.upper()}_signature.json")
        return os.path.exists(path)

    # ---------------- Drug Score 缓存 ----------------

    def get_drug_scores(self, gene_name: str, method: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(
            DRUG_SCORE_CACHE_DIR,
            f"{gene_name.upper()}_{method.lower()}_drug_scores.json"
        )
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def save_drug_scores(self, gene_name: str, method: str, data: Dict[str, Any]):
        path = os.path.join(
            DRUG_SCORE_CACHE_DIR,
            f"{gene_name.upper()}_{method.lower()}_drug_scores.json"
        )
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def drug_scores_exist(self, gene_name: str, method: str) -> bool:
        path = os.path.join(
            DRUG_SCORE_CACHE_DIR,
            f"{gene_name.upper()}_{method.lower()}_drug_scores.json"
        )
        return os.path.exists(path)

    # ---------------- 通用清理 ----------------

    def clear_gene(self, gene_name: str) -> bool:
        """清除某基因的所有缓存，返回是否删了东西"""
        gene_upper = gene_name.upper()
        deleted = False

        sig_path = os.path.join(SIGNATURE_CACHE_DIR, f"{gene_upper}_signature.json")
        if os.path.exists(sig_path):
            os.remove(sig_path)
            deleted = True

        for method in ['xsum', 'wtcs']:
            drug_path = os.path.join(
                DRUG_SCORE_CACHE_DIR,
                f"{gene_upper}_{method}_drug_scores.json"
            )
            if os.path.exists(drug_path):
                os.remove(drug_path)
                deleted = True

        return deleted

    def list_cached_genes(self) -> list:
        """列出所有已缓存 signature 的基因"""
        genes = []
        for f in os.listdir(SIGNATURE_CACHE_DIR):
            if f.endswith('_signature.json'):
                genes.append(f.replace('_signature.json', ''))
        return sorted(genes)

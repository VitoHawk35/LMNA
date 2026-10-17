#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
药物预聚合矩阵
把每个药物的多个实例聚合成一个中位数向量，加速筛药。
"""

import os
import numpy as np
import pandas as pd

from data_provider import IDataProvider
from config import CACHE_DIR

_DRUG_MEDIAN_PATH = os.path.join(CACHE_DIR, "_drug_median_matrix.npy")
_DRUG_NAMES_PATH = os.path.join(CACHE_DIR, "_drug_names.csv")


def _ensure_drug_median_cache(provider: IDataProvider) -> tuple:
    """
    构建或读取药物中位数矩阵缓存。

    Returns:
        (matrix, names)
        matrix: np.ndarray, shape=(978, n_drugs)
        names: list of drug names
    """
    if os.path.exists(_DRUG_MEDIAN_PATH) and os.path.exists(_DRUG_NAMES_PATH):
        matrix = np.load(_DRUG_MEDIAN_PATH, mmap_mode='r')
        names = pd.read_csv(_DRUG_NAMES_PATH)['drug_name'].tolist()
        if matrix.shape[1] == len(names):
            print(f"[DrugMedianCache] 从缓存加载: {matrix.shape[1]} 种药物")
            return matrix, names

    print("[DrugMedianCache] 首次构建药物中位数矩阵...")
    drug_df = provider.get_drug_samples()
    drug_name_map = provider.get_drug_name_map()

    # 按药物名分组，收集 sig_id 索引
    drug_to_sigs = {}
    for sid in drug_df['sig_id'].tolist():
        name = drug_name_map.get(sid)
        if pd.isna(name):
            continue
        drug_to_sigs.setdefault(name, []).append(sid)

    drug_names = sorted(drug_to_sigs.keys())
    print(f"[DrugMedianCache] 共 {len(drug_names)} 种独特药物")

    # 分批读取并计算中位数
    BATCH_SIZE = 1000  # 药物数
    all_medians = []

    for start in range(0, len(drug_names), BATCH_SIZE):
        end = min(start + BATCH_SIZE, len(drug_names))
        batch_names = drug_names[start:end]
        batch_sigs = []
        batch_counts = []
        for name in batch_names:
            sigs = drug_to_sigs[name]
            batch_sigs.extend(sigs)
            batch_counts.append(len(sigs))

        # 读取这些药物所有实例的表达矩阵
        matrix = provider.get_drug_expression_matrix(batch_sigs)

        # 按药物分组取中位数
        offset = 0
        batch_medians = np.zeros((matrix.shape[0], len(batch_names)), dtype=np.float32)
        for i, count in enumerate(batch_counts):
            sub = matrix[:, offset:offset+count]
            batch_medians[:, i] = np.median(sub, axis=1)
            offset += count

        all_medians.append(batch_medians)
        print(f"[DrugMedianCache] 进度: {end}/{len(drug_names)}")

    full_matrix = np.hstack(all_medians)
    np.save(_DRUG_MEDIAN_PATH, full_matrix)
    pd.DataFrame({'drug_name': drug_names}).to_csv(_DRUG_NAMES_PATH, index=False)

    return np.load(_DRUG_MEDIAN_PATH, mmap_mode='r'), drug_names


def get_drug_median_matrix(provider: IDataProvider) -> tuple:
    """获取药物中位数矩阵和药物名列表。"""
    return _ensure_drug_median_cache(provider)

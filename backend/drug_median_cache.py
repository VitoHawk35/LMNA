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
from cache_manager import exclusive_file_lock, replace_file_with_retry
from config import CACHE_DIR, ALGO_VERSION


# 可选的显式路径覆盖（仅测试/特殊部署使用）；生产默认走下方版本化路径。
_DRUG_MEDIAN_PATH = None
_DRUG_NAMES_PATH = None


def _drug_median_cache_paths() -> tuple:
    """药物中位数缓存路径：带算法版本，避免读到旧算法/旧数据的结果。"""
    if _DRUG_MEDIAN_PATH and _DRUG_NAMES_PATH:
        return _DRUG_MEDIAN_PATH, _DRUG_NAMES_PATH
    stem = os.path.join(CACHE_DIR, f"_drug_median_matrix.v{ALGO_VERSION}")
    return stem + ".npy", os.path.join(
        CACHE_DIR, f"_drug_names.v{ALGO_VERSION}.csv"
    )


def _try_load_cache(path: str, names_path: str):
    """缓存存在且矩阵列数与药名数一致时返回 (matrix, names)，否则 None。"""
    if not (os.path.exists(path) and os.path.exists(names_path)):
        return None
    try:
        matrix = np.load(path, mmap_mode='r')
        names = pd.read_csv(names_path)['drug_name'].tolist()
    except (
        OSError, ValueError, KeyError, EOFError,
        pd.errors.EmptyDataError, pd.errors.ParserError,
    ):
        return None
    if matrix.ndim != 2 or matrix.shape[1] != len(names):
        return None
    return matrix, names


def _ensure_drug_median_cache(provider: IDataProvider) -> tuple:
    """
    构建或读取药物中位数矩阵缓存。
    文件名带 ALGO_VERSION；构建时对 <缓存文件>.lock 加排他锁并双重检查。

    Returns:
        (matrix, names)
        matrix: np.ndarray, shape=(978, n_drugs)
        names: list of drug names
    """
    path, names_path = _drug_median_cache_paths()

    loaded = _try_load_cache(path, names_path)
    if loaded is not None:
        print(f"[DrugMedianCache] 从缓存加载: {loaded[0].shape[1]} 种药物")
        return loaded

    with exclusive_file_lock(path + ".lock"):
        # 双重检查：等待锁期间别的进程可能已经构建完成。
        loaded = _try_load_cache(path, names_path)
        if loaded is not None:
            print(f"[DrugMedianCache] 从缓存加载（等待锁后）: {loaded[0].shape[1]} 种药物")
            return loaded

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

        # 临时文件 + 原子替换，避免读取方读到半截矩阵。
        tmp_matrix = f"{path}.tmp.{os.getpid()}.npy"
        tmp_names = f"{names_path}.tmp.{os.getpid()}"
        try:
            np.save(tmp_matrix, full_matrix)
            pd.DataFrame({'drug_name': drug_names}).to_csv(tmp_names, index=False)
            replace_file_with_retry(tmp_matrix, path)
            replace_file_with_retry(tmp_names, names_path)
        finally:
            for tmp in (tmp_matrix, tmp_names):
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass

    return np.load(path, mmap_mode='r'), drug_names


def get_drug_median_matrix(provider: IDataProvider) -> tuple:
    """获取药物中位数矩阵和药物名列表。"""
    return _ensure_drug_median_cache(provider)

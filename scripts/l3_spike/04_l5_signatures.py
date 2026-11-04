#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7e 阶段 1 · 任务 3（L5 侧）：TOP2A / LMNA / CDK4（交叉验证）的 L5 签名重算。

运行方式（在服务器上）：
    LMNA_BACKEND=/home/keji/l3_tmp/l5backend \
    CMAP_DATA_DIR=/home/keji/cmap_v2_data \
    LMNA_CACHE_DIR=/home/keji/l3_tmp/l5cache \
    BOOTSTRAP_N=100000 FDR_THRESHOLD=0.001 KS_THRESHOLD=0.2 \
    FAST_MODE_TOP_N=0 DATA_PROVIDER=l5 LINCS_INTEGRITY_MODE=off \
    ~/miniconda3/envs/cmap/bin/python -B 04_l5_signatures.py

- 代码：worktree feat/l3-signature 的 backend 副本（RULE_VERSION 4.5，
  与 ~/lmna_v3_cache 里 b031a48b8a 缓存签名同代；参数哈希应与现网 v2 一致）。
- 数据：生产 cmap_v2_data 只读；LINCS_INTEGRITY_MODE=off 仅跳过启动自检
  （列序/行序修复已按 BACKEND_SITUATION 验收，本脚本不改任何生产文件）。
- 缓存：LMNA_CACHE_DIR 指向 l3_tmp/l5cache（内含指向 ~/lmna_v2_cache 秩矩阵
  的符号链接，只读复用）；签名 JSON 写到 l3_tmp，不碰生产缓存。
- CDK4 用于与 ~/lmna_v3_cache 的缓存签名做逐字段交叉验证。

输出：results/l5/<GENE>_signature.json + results/04_l5_summary.json
"""
import json
import os
import sys
import time

BACKEND = os.environ.get("LMNA_BACKEND", "/home/keji/l3_tmp/l5backend")
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

OUT_RESULTS = "/home/keji/l3_tmp/results"
OUT_L5 = os.path.join(OUT_RESULTS, "l5")
os.makedirs(OUT_L5, exist_ok=True)

GENES = ["TOP2A", "LMNA", "CDK4"]   # CDK4 仅作缓存交叉验证

t0 = time.time()
from l5_provider import L5Provider          # noqa: E402
from signature_engine import SignatureEngine  # noqa: E402
import config  # noqa: E402

print(f"[env] BOOTSTRAP_N={config.BOOTSTRAP_N} FDR={config.FDR_THRESHOLD} "
      f"KS={config.KS_THRESHOLD} FAST={config.FAST_MODE_TOP_N} "
      f"CACHE={config.CACHE_DIR} DATA={config.DATA_DIR}", flush=True)

provider = L5Provider()
engine = SignatureEngine(provider)

summary = {}
for gene in GENES:
    t = time.time()
    sig = engine.compute_signature(gene)
    qc = sig.get("qc", {})
    summary[gene] = {
        "source": f"recomputed by worktree backend @ l3_tmp, "
                  f"RULE_VERSION={qc.get('rule_version')}",
        "n_samples": sig["n_samples"],
        "n_hairpins": sig.get("n_hairpins"),
        "n_cells": sig.get("n_cells"),
        "n_sig": sig.get("n_sig"),
        "up_genes": sig.get("up_genes"),
        "down_genes": sig.get("down_genes"),
        "loho_jaccard_min": sig.get("loho_jaccard_min"),
        "target_ks": (sig.get("ks_scores") or {}).get(gene),
        "grade": qc.get("grade"),
        "bootstrap_n": sig.get("bootstrap_n"),
        "params": sig.get("params"),
        "elapsed_s": round(time.time() - t, 1),
    }
    with open(os.path.join(OUT_L5, f"{gene}_signature.json"), "w",
              encoding="utf-8") as fp:
        json.dump(sig, fp, ensure_ascii=False)
    print(f"[{time.time()-t0:7.1f}s] {gene} 完成 "
          f"(n_sig={summary[gene]['n_sig']}, grade={summary[gene]['grade']})",
          flush=True)

with open(os.path.join(OUT_RESULTS, "04_l5_summary.json"), "w",
          encoding="utf-8") as fp:
    json.dump(summary, fp, ensure_ascii=False, indent=2)
print(f"总耗时 {(time.time()-t0)/60:.1f} 分钟", flush=True)

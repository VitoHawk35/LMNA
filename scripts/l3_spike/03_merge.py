#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""合并 03 的单基因分片结果为 03_l3_signatures.json。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import GENES, OUT_RESULTS

merged = {}
for gene in GENES:
    p = os.path.join(OUT_RESULTS, f"03_l3_{gene}.json")
    with open(p, encoding="utf-8") as fp:
        merged.update(json.load(fp))
out = os.path.join(OUT_RESULTS, "03_l3_signatures.json")
with open(out, "w", encoding="utf-8") as fp:
    json.dump(merged, fp, ensure_ascii=False, indent=2)
print("merged ->", out, list(merged))

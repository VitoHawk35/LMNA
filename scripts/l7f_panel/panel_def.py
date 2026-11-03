#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L7f 阶段1 · 靶点面板定义（≥20 靶点 + 难度/阴性对照）

构成：
- 基准 10：CDK4/EGFR/MTOR/PIK3CA/AKT1/BRAF/JAK2/HDAC1/TP53/MYC
  （金标准药物清单沿用 round2/verification/多基因测试-权威基准.md，
  来源 = Drug Repurposing Hub(clue.io) MoA 注释 / 药品说明书靶点 / 文献共识）
- 项目对照：LMNA（LMNA 项目同名基因，无直接抑制剂 → 难度对照）
- 扩展 10：CDK6/CDK2/AURKA/PLK1/ERBB2/ALK/MET/FGFR1/MAP2K1/CDK9
  （同一整理口径；预期覆盖绿/黄/空隙区/红各档）

别名字典：组内任一变体命中 pert_iname（小写精确匹配）即算该药在场，
与 scripts/l3_exp1_accuracy.py 的 GOLD 口径一致。

expected 字段是面板设计时的**预期档位**（用于验收面板覆盖面，不参与判档）：
- green：强 KD 签名（cell cycle / 通路枢纽）
- gap：刻意挑选预期落入空隙区 n_sig∈[5,20) × LOHO∈[0.3,0.5) 的中等靶点
  （RTK 类与部分 CDK 在 LINCS KD 中签名偏弱，L5 时代 n_sig 多在 10–25）
- red：难度/阴性对照（无直接抑制剂或签名历来不稳）
"""

# 每个靶点：
#   gold:     金标准药物别名组（空列表 = 无金标准 → 难度/阴性对照）
#   role:     baseline | project | extension
#   expected: green | yellow | gap | red（面板设计预期，仅供覆盖面验收）
#   source:   金标准清单出处
PANEL = {
    # ---------------- 基准 10（权威基准文档原有清单，逐项保留） ----------------
    "CDK4": {
        "gold": [
            {"palbociclib", "pd-0332991"}, {"ribociclib", "lee011"},
            {"abemaciclib", "ly2835219"}, {"dinaciclib", "sch727965"},
            {"alvocidib", "flavopiridol"}, {"roscovitine", "seliciclib", "cyc202"},
        ],
        "role": "baseline", "expected": "green",
        "source": "权威基准（DRH MoA：CDK4/6 选择性 + pan-CDK）；"
                  "palbociclib 说明书靶点 CDK4/6",
    },
    "EGFR": {
        "gold": [
            {"gefitinib"}, {"erlotinib"}, {"afatinib", "bibw2992"},
            {"dacomitinib", "pf-00299804"}, {"lapatinib"},
            {"canertinib", "ci-1033"}, {"pelitinib", "ekb-569"},
        ],
        "role": "baseline", "expected": "gap",
        "source": "权威基准（EGFR-TKI 说明书靶点 + pan-ErbB）；"
                  "L7e 阶段2 实测 L3 n_sig=18/LOHO=0.385 正落空隙",
    },
    "MTOR": {
        "gold": [
            {"sirolimus", "rapamycin"}, {"everolimus"}, {"temsirolimus"},
            {"torin-1", "torin1"}, {"torin-2", "torin2"},
            {"azd8055"}, {"dactolisib", "bez235", "nvp-bez235"},
            {"pi-103", "pi103"}, {"wortmannin"}, {"ly294002"},
        ],
        "role": "baseline", "expected": "green",
        "source": "权威基准（mTORC1i/mTOR-Ki 说明书与文献 + pan-PI3K）",
    },
    "PIK3CA": {
        "gold": [
            {"alpelisib", "byl719"}, {"pictilisib", "gdc-0941"},
            {"buparlisib", "bkm120", "nvp-bkm120"},
            {"idelalisib", "gs-1101", "cal-101"},
            {"pi-103", "pi103"}, {"dactolisib", "bez235", "nvp-bez235"},
        ],
        "role": "baseline", "expected": "green",
        "source": "权威基准（PI3K 抑制剂 DRH MoA + alpelisib 说明书靶点 PIK3CA）",
    },
    "AKT1": {
        "gold": [
            {"mk-2206", "mk2206"}, {"capivasertib", "azd5363"},
            {"ipatasertib", "gdc-0068"}, {"perifosine"},
            {"tricirubine", "triciribine"},
        ],
        "role": "baseline", "expected": "yellow",
        "source": "权威基准（AKT 抑制剂 DRH MoA / 文献共识）",
    },
    "BRAF": {
        "gold": [
            {"vemurafenib", "plx4032"}, {"dabrafenib", "gsk2118436"},
            {"sorafenib"}, {"plx-4720", "plx4720"},
            {"trametinib", "gsk1120212"}, {"selumetinib", "azd6244"},
            {"pd-0325901", "pd0325901"}, {"ci-1040", "ci1040", "pd184352"},
        ],
        "role": "baseline", "expected": "yellow",
        "source": "权威基准（RAF 抑制剂 + 下游 MEK 抑制剂属合理命中）",
    },
    "JAK2": {
        "gold": [
            {"ruxolitinib", "incb018424"},
            {"fedratinib", "tg101348", "sar302503"},
            {"momelotinib", "gs-0387", "cyt387"},
            {"baricitinib", "ly3009104", "incb028050"},
            {"azd1480"}, {"lestaurtinib", "cep-701"},
        ],
        "role": "baseline", "expected": "yellow",
        "source": "权威基准（JAK2/JAK 抑制剂说明书靶点 + DRH MoA）",
    },
    "HDAC1": {
        "gold": [
            {"vorinostat", "saha"}, {"panobinostat", "lbh589"},
            {"trichostatin-a", "trichostatin a"}, {"entinostat", "ms-275", "sndx-275"},
            {"mocetinostat", "mgcd0103"}, {"valproic-acid", "valproic acid"},
            {"scriptaid"},
        ],
        "role": "baseline", "expected": "green",
        "source": "权威基准（HDAC 抑制剂 DRH MoA；注意连通性图谱中普遍高分、"
                  "特异性弱）",
    },
    "TP53": {
        "gold": [],
        "role": "baseline", "expected": "red",
        "source": "权威基准：无金标准（无直接抑制剂；nutlin 类为 p53 激活剂，"
                  "理论不应逆转 KD 签名）→ 阴性/难度对照",
    },
    "MYC": {
        "gold": [],
        "role": "baseline", "expected": "red",
        "source": "权威基准：无直接抑制剂（JQ1 等 BRD4i 为间接机制）→ 难度对照",
    },
    # ---------------- 项目对照 ----------------
    "LMNA": {
        "gold": [],
        "role": "project", "expected": "red",
        "source": "LMNA 项目同名基因；无直接抑制剂（核纤层结构蛋白，"
                  "不可成药）→ 难度对照；L7e spike 实测 93 样本/3 hairpin",
    },
    # ---------------- 扩展 10（同一整理口径：DRH MoA / 说明书 / 文献共识） ----------------
    "CDK6": {
        "gold": [
            {"palbociclib", "pd-0332991"}, {"ribociclib", "lee011"},
            {"abemaciclib", "ly2835219"},
        ],
        "role": "extension", "expected": "green",
        "source": "DRH MoA + 说明书：palbociclib/ribociclib/abemaciclib "
                  "均为 CDK4/6 选择性抑制剂",
    },
    "CDK2": {
        "gold": [
            {"dinaciclib", "sch727965"},
            {"roscovitine", "seliciclib", "cyc202"},
            {"alvocidib", "flavopiridol"}, {"azd5438"},
        ],
        "role": "extension", "expected": "gap",
        "source": "DRH MoA：dinaciclib(CDK1/2/5/9)、roscovitine(CDK2/5/7/9)、"
                  "flavopiridol(pan-CDK)、AZD5438(CDK2/9)",
    },
    "AURKA": {
        "gold": [
            {"alisertib", "mln8237"},
            {"tozasertib", "vx-680", "mk-0457"},
            {"danusertib", "pha-739358"}, {"enmd-2076"},
        ],
        "role": "extension", "expected": "green",
        "source": "DRH MoA：alisertib(AURKA 选择性)、tozasertib/danusertib"
                  "(pan-Aurora)、ENMD-2076(AURKA/VEGFR)；细胞周期 KD 签名强",
    },
    "PLK1": {
        "gold": [
            {"volasertib", "bi-6727", "bi6727"}, {"bi-2536", "bi2536"},
            {"rigosertib", "on-01910", "on01910"}, {"gsk461364"},
        ],
        "role": "extension", "expected": "green",
        "source": "DRH MoA：volasertib/BI-2536/GSK461364(PLK1 选择性)、"
                  "rigosertib(PLK1/PI3K)；细胞周期 KD 签名强",
    },
    "ERBB2": {
        "gold": [
            {"lapatinib"}, {"neratinib", "hki-272"},
            {"afatinib", "bibw2992"}, {"canertinib", "ci-1033"},
            {"pelitinib", "ekb-569"},
        ],
        "role": "extension", "expected": "gap",
        "source": "DRH MoA + 说明书：lapatinib(EGFR/HER2)、neratinib/afatinib/"
                  "canertinib(pan-ErbB)；RTK 类 KD 签名中等，候选空隙区",
    },
    "ALK": {
        "gold": [
            {"crizotinib", "pf-02341066"}, {"ceritinib", "ldk378"},
            {"alectinib", "ch5424802", "ro5424802"},
            {"lorlatinib", "pf-06463922"}, {"nvp-tae684", "tae684"},
        ],
        "role": "extension", "expected": "gap",
        "source": "DRH MoA + 说明书：crizotinib/ceritinib/alectinib/lorlatinib "
                  "ALK-TKI；NVP-TAE684 文献 ALK 工具药；RTK 候选空隙区",
    },
    "MET": {
        "gold": [
            {"crizotinib", "pf-02341066"}, {"cabozantinib", "xl184", "bms-907351"},
            {"foretinib", "xl880", "gsk1363089"}, {"pha-665752", "pha665752"},
        ],
        "role": "extension", "expected": "gap",
        "source": "DRH MoA + 说明书：crizotinib(ALK/MET)、cabozantinib/"
                  "foretinib(含 MET 的多激酶)、PHA-665752(MET 工具药)；"
                  "RTK 候选空隙区",
    },
    "FGFR1": {
        "gold": [
            {"ponatinib", "ap24534"}, {"infigratinib", "bgj398", "nvp-bgj398"},
            {"azd4547"}, {"pd173074", "pd-173074"},
            {"dovitinib", "tki258", "chir-258"},
        ],
        "role": "extension", "expected": "gap",
        "source": "DRH MoA：ponatinib(含 FGFR 的多激酶)、infigratinib/AZD4547/"
                  "PD173074(FGFR1-3 选择性)、dovitinib(FGFR/VEGFR)；RTK 候选空隙区",
    },
    "MAP2K1": {
        "gold": [
            {"trametinib", "gsk1120212"},
            {"selumetinib", "azd6244", "arry-142886"},
            {"cobimetinib", "gdc-0973", "xl518"},
            {"ci-1040", "ci1040", "pd184352"},
            {"pd-0325901", "pd0325901"},
            {"refametinib", "rdea119", "bay-86-9766"},
            {"binimetinib", "mek162", "arry-162"},
        ],
        "role": "extension", "expected": "green",
        "source": "DRH MoA + 说明书：trametinib/selumetinib/cobimetinib "
                  "MEK1/2 抑制剂（MAP2K1 = MEK1）；通路枢纽 KD 签名强",
    },
    "CDK9": {
        "gold": [
            {"alvocidib", "flavopiridol"}, {"dinaciclib", "sch727965"},
            {"sns-032", "bms-387032"}, {"atuveciclib", "bay-1143572", "bay1143572"},
        ],
        "role": "extension", "expected": "yellow",
        "source": "DRH MoA：flavopiridol(CDK9 为主 pan-CDK)、dinaciclib(CDK1/2/5/9)、"
                  "SNS-032(CDK2/7/9)、atuveciclib(CDK9 选择性)",
    },
}

TARGETS = sorted(PANEL.keys())
assert len(TARGETS) >= 20, f"面板不足 20 靶点: {len(TARGETS)}"

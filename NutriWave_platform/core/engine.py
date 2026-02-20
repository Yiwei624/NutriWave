\
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import random

@dataclass
class UserRequest:
    lang: str
    product_type: str
    base_id: str
    texture: str
    goals: List[str]
    constraints: Dict[str, Any]

def _score_strain(strain: Dict[str, Any], goals: List[str]) -> int:
    tags = set(strain.get("benefit_tags", []))
    return sum(2 if g in tags else 0 for g in goals)

def shortlist_strains(data: Dict[str, Any], goals: List[str], k: int = 3) -> List[Dict[str, Any]]:
    strains = data.get("strains", [])
    ranked = sorted(strains, key=lambda s: _score_strain(s, goals), reverse=True)
    return ranked[:max(1, min(k, len(ranked)))] if ranked else []

def build_candidate_formulations(
    data: Dict[str, Any],
    req: UserRequest,
    n: int = 3,
    customer_profile: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    bases = {b["id"]: b for b in data.get("bases", [])}
    base = bases.get(req.base_id, {"id": req.base_id, "default_protein_pct": 10.0, "name_en": req.base_id, "name_zh": req.base_id})

    suppliers = {s["supplier_id"]: s for s in data.get("suppliers", [])}
    target = data.get("targets", {}).get(req.texture, {}).get(req.lang, {})

    strains_raw = data.get("strains", [])
    strains = shortlist_strains(data, req.goals, k=3) or strains_raw[:1] or [{
        "strain_id":"TBD-001","name_zh":"待补充菌株 (TBD)","name_en":"Strain TBD","supplier_id":"KT","benefit_tags":[]
    }]

    protein_pct = float(base.get("default_protein_pct", 10.0))
    stabilizer = 0.30 if req.texture != "refreshing" else 0.15
    sweetener = 0.50 if req.texture != "refreshing" else 0.40
    if req.texture == "thick":
        stabilizer, sweetener = 0.45, 0.55

    if customer_profile:
        sm = customer_profile.get("sweet_mean")
        tm = customer_profile.get("texture_mean")
        if sm is not None and sm > 3.5:
            sweetener += 0.05
        if tm is not None and tm > 3.5:
            stabilizer += 0.05

    random.seed(42)
    sweetener_levels = [max(0.2, sweetener - 0.05), sweetener, sweetener + 0.05]
    stabilizer_levels = [max(0.10, stabilizer - 0.05), stabilizer, stabilizer + 0.05]
    combos = [(s, st) for s in sweetener_levels for st in stabilizer_levels]
    random.shuffle(combos)

    def sup_name(sid: str) -> str:
        return suppliers.get(sid, {}).get("name", sid)

    variants: List[Dict[str, Any]] = []
    for i in range(min(n, len(combos))):
        s_lv, st_lv = combos[i]
        strain = strains[i % len(strains)]
        water = 100.0 - protein_pct - s_lv - st_lv

        desc_zh = f"Clean label: 去豆腥、甜香风味、{req.texture}口感。"
        desc_en = f"Clean label: reduced beany, sweet notes, {req.texture} texture."
        desc = desc_zh if req.lang == "zh" else desc_en

        variants.append({
            "product": {
                "name_zh": f"{base.get('name_zh','')} 发酵酸奶（{req.texture}）",
                "name_en": f"{base.get('name_en','')} fermented yogurt ({req.texture})",
                "type": req.product_type
            },
            "description": desc,
            "formula_100kg": [
                {"item_zh": "水", "item_en": "Water", "kg": round(water, 2)},
                {"item_zh": f"{base.get('name_zh','')}蛋白", "item_en": f"{base.get('name_en','')} protein",
                 "kg": round(protein_pct, 2), "supplier": "TBD"},
                {"item_zh": "甜味剂", "item_en": "Sweetener", "kg": round(s_lv, 2), "supplier": "TBD"},
                {"item_zh": "稳定剂/淀粉", "item_en": "Stabilizer/Starch", "kg": round(st_lv, 2), "supplier": "TBD"},
                {"item_zh": "菌株", "item_en": "Strain",
                 "id": strain.get("strain_id"), "name_zh": strain.get("name_zh"), "name_en": strain.get("name_en"),
                 "supplier": sup_name(strain.get("supplier_id", ""))}
            ],
            "process": {
                "heat_treat": "85°C 10 min",
                "cool_to_inoculation": "42°C",
                "fermentation": "42°C 6–10 h (stop at pH 4.4–4.6)",
                "post": "4°C cold storage 12–24 h"
            },
            "targets": target,
            "rationale": {
                "goals": req.goals,
                "strain_tags": strain.get("benefit_tags", []),
                "customer_profile_used": bool(customer_profile)
            }
        })
    return variants

def build_minidoe_plan(req: UserRequest) -> Dict[str, Any]:
    if req.lang == "zh":
        return {"小试方法": ["固定终止 pH（例如 4.6）", "记录 pH–时间曲线", "每个候选 n=2 重复", "测：分水率、G'、τy、滞回"]}
    return {"mini_test_plan": ["Hold endpoint pH constant (e.g., 4.6)", "Record pH–time", "n=2 replicates per candidate", "Measure syneresis, G', τy, hysteresis"]}

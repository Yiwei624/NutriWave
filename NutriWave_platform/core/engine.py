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
    customer_profile: Optional[Dict[str, Any]] = None
    learning_scores: Optional[Dict[str, Any]] = None

def _score_item(item: Dict[str, Any], goals: List[str], learning_scores: Optional[Dict[str, Any]]) -> float:
    tags = set(item.get("benefit_tags", []))
    score = sum(2.0 if g in tags else 0.0 for g in goals)
    if learning_scores:
        key = item.get("strain_combo_id") or item.get("strain_id")
        hist = (learning_scores.get("strain_combo_scores", {}) or {}).get(key)
        if hist is not None:
            score += float(hist) / 50.0
    return score

def shortlist_combos(data: Dict[str, Any], goals: List[str], k: int, learning_scores: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    combos = [s for s in data.get("strains", []) if s.get("kind") == "combo"]
    ranked = sorted(combos, key=lambda x: _score_item(x, goals, learning_scores), reverse=True)
    return ranked[:max(1, min(k, len(ranked)))] if ranked else []

def pick_default_ingredients(data: Dict[str, Any]) -> Dict[str, Any]:
    ing = data.get("ingredients", [])
    def first_cat(cat: str):
        for it in ing:
            if it.get("category") == cat:
                return it
        return None
    return {"protein": first_cat("protein"), "sweetener": first_cat("sweetener"), "stabilizer": first_cat("stabilizer")}

def build_candidate_formulations(data: Dict[str, Any], req: UserRequest, n: int = 3) -> List[Dict[str, Any]]:
    bases = {b["id"]: b for b in data.get("bases", [])}
    base = bases.get(req.base_id, {"id": req.base_id, "default_protein_pct": 10.0, "name_en": req.base_id, "name_zh": req.base_id})
    suppliers = {s["supplier_id"]: s for s in data.get("suppliers", [])}
    targets = data.get("targets", {}).get(req.texture, {}).get(req.lang, {})

    combos = shortlist_combos(data, req.goals, k=3, learning_scores=req.learning_scores) or [s for s in data.get("strains", []) if s.get("kind") == "combo"][:1]
    if not combos:
        combos = [{"kind":"combo","strain_combo_id":"COMBO-TBD","name_zh":"待补充复合菌 (TBD)","name_en":"Combo TBD","supplier_id":"KT","benefit_tags":[]}]
    protein_pct = float(base.get("default_protein_pct", 10.0))

    if req.texture == "thick":
        stabilizer, sweetener = 0.45, 0.55
    elif req.texture == "refreshing":
        stabilizer, sweetener = 0.15, 0.40
    else:
        stabilizer, sweetener = 0.30, 0.50

    cp = req.customer_profile or {}
    if cp.get("sweet_mean") is not None and cp["sweet_mean"] > 3.5:
        sweetener += 0.05
    if cp.get("texture_mean") is not None and cp["texture_mean"] > 3.5:
        stabilizer += 0.05

    random.seed(42)
    sweetener_levels = [max(0.2, sweetener - 0.05), sweetener, sweetener + 0.05]
    stabilizer_levels = [max(0.10, stabilizer - 0.05), stabilizer, stabilizer + 0.05]
    grid = [(s, st) for s in sweetener_levels for st in stabilizer_levels]
    random.shuffle(grid)

    ing_pick = pick_default_ingredients(data)

    def sup_name(sid: str) -> str:
        return suppliers.get(sid, {}).get("name", sid)

    out = []
    for i in range(min(n, len(grid))):
        s_lv, st_lv = grid[i]
        combo = combos[i % len(combos)]
        water = 100.0 - protein_pct - s_lv - st_lv
        desc = (f"Clean label: 去豆腥、甜香风味、{req.texture}口感。" if req.lang=="zh"
                else f"Clean label: reduced beany, sweet notes, {req.texture} texture.")
        formulation = {
            "base_id": req.base_id,
            "basis": "per_100kg",
            "ingredients": [
                {"ingredient_id": (ing_pick["protein"] or {}).get("ingredient_id","TBD"),
                 "name_zh": (ing_pick["protein"] or {}).get("name_zh","TBD"),
                 "name_en": (ing_pick["protein"] or {}).get("name_en","TBD"),
                 "dosage_kg": round(protein_pct, 2)},
                {"ingredient_id": (ing_pick["sweetener"] or {}).get("ingredient_id","TBD"),
                 "name_zh": (ing_pick["sweetener"] or {}).get("name_zh","TBD"),
                 "name_en": (ing_pick["sweetener"] or {}).get("name_en","TBD"),
                 "dosage_kg": round(s_lv, 2)},
                {"ingredient_id": (ing_pick["stabilizer"] or {}).get("ingredient_id","TBD"),
                 "name_zh": (ing_pick["stabilizer"] or {}).get("name_zh","TBD"),
                 "name_en": (ing_pick["stabilizer"] or {}).get("name_en","TBD"),
                 "dosage_kg": round(st_lv, 2)},
                {"ingredient_id": "WATER", "name_zh": "水", "name_en": "Water", "dosage_kg": round(max(0.0, water), 2)}
            ],
            "clean_label": True,
            "version": "v1"
        }
        out.append({
            "product": {"type": req.product_type, "name_zh": f"{base.get('name_zh','')}酸奶({req.texture})", "name_en": f"{base.get('name_en','')} yogurt ({req.texture})"},
            "strain_combo": {"id": combo.get("strain_combo_id"), "name_zh": combo.get("name_zh"), "name_en": combo.get("name_en"),
                             "supplier": sup_name(combo.get("supplier_id","")), "benefit_tags": combo.get("benefit_tags", [])},
            "description": desc,
            "formulation": formulation,
            "process": {"heat_treat": "85°C 10 min", "inoculation": combo.get("inoculation_pct","TBD"),
                        "fermentation": "42°C 6–10 h (stop at pH 4.4–4.6)"},
            "targets": targets,
            "rationale": {"goals": req.goals, "history_n_used": (req.learning_scores or {}).get("n_used", 0)}
        })
    return out

def build_minidoe_plan(req: UserRequest) -> Dict[str, Any]:
    if req.lang == "zh":
        return {"小试方法": ["3候选×n=2重复", "固定终止pH(如4.6)", "记录pH-时间曲线", "24h后测syneresis",
                           "流变按Row2方法，标注Λ/regime，低质量不进入学习"]}
    return {"mini_test_plan": ["3 candidates × n=2", "Hold endpoint pH (e.g., 4.6)", "Record pH-time", "Syneresis after 24h",
                               "Rheology per Row2; label Lambda/regime; exclude low-quality from learning"]}

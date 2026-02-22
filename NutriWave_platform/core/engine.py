\
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import random
from core.modeling import predict

@dataclass
class UserRequest:
    lang: str
    product_type: str
    base_id: str
    texture: str
    brief: str
    customer_profile: Optional[Dict[str, Any]] = None

def infer_goals(brief: str, texture: str) -> List[str]:
    b = (brief or "").lower()
    goals = []
    if ("豆腥" in (brief or "")) or ("beany" in b) or ("off-flavor" in b):
        goals.append("anti_beany")
    if ("甜" in (brief or "")) or ("sweet" in b):
        goals.append("sweet_notes")
    if texture in ["soft", "thick"]:
        goals.append("eps")
    return goals

def choose_default_formulation(data: Dict[str, Any], base_id: str, texture: str, customer_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ing = data.get("ingredients", [])
    def first(cat: str):
        for it in ing:
            if it.get("category") == cat:
                return it
        return None
    protein = first("protein")
    sweet = first("sweetener")
    stab = first("stabilizer")

    bases = {b["id"]: b for b in data.get("bases", [])}
    protein_kg = float(bases.get(base_id, {}).get("default_protein_pct", 10.0))

    if texture == "thick":
        sweet_kg, stab_kg = 0.55, 0.45
    elif texture == "refreshing":
        sweet_kg, stab_kg = 0.40, 0.15
    else:
        sweet_kg, stab_kg = 0.50, 0.30

    cp = customer_profile or {}
    if cp.get("sweet_mean") is not None and cp["sweet_mean"] > 3.5:
        sweet_kg += 0.05
    if cp.get("texture_mean") is not None and cp["texture_mean"] > 3.5:
        stab_kg += 0.05

    water = max(0.0, 100.0 - (protein_kg + sweet_kg + stab_kg))

    return {
        "base_id": base_id,
        "basis": "per_100kg",
        "version": "engine_v1",
        "ingredients": [
            {"ingredient_id": (protein or {}).get("ingredient_id", "TBD"), "dosage_kg": round(protein_kg, 2)},
            {"ingredient_id": (sweet or {}).get("ingredient_id", "TBD"), "dosage_kg": round(sweet_kg, 2)},
            {"ingredient_id": (stab or {}).get("ingredient_id", "TBD"), "dosage_kg": round(stab_kg, 2)},
            {"ingredient_id": "WATER", "dosage_kg": round(water, 2)},
        ],
    }

def generate_candidates(data: Dict[str, Any], req: UserRequest, model: Optional[Dict[str, Any]] = None, k: int = 3) -> List[Dict[str, Any]]:
    base_form = choose_default_formulation(data, req.base_id, req.texture, req.customer_profile)
    goals = infer_goals(req.brief, req.texture)

    grid = [(-0.05, 0.0), (0.0, 0.0), (0.05, 0.0), (0.0, -0.05), (0.0, 0.05)]
    random.seed(42)
    random.shuffle(grid)

    combos = sorted(
        data.get("strains", []),
        key=lambda c: sum(2 for g in goals if g in set(c.get("benefit_tags", []))),
        reverse=True
    ) or []

    out = []
    for idx in range(k):
        d_s, d_st = grid[idx % len(grid)]
        form = {"base_id": base_form["base_id"], "basis": base_form["basis"], "version": base_form["version"],
                "ingredients": [dict(x) for x in base_form["ingredients"]]}

        # assume index 1 sweetener, 2 stabilizer (seed default); later you can match by category
        form["ingredients"][1]["dosage_kg"] = round(max(0.2, form["ingredients"][1]["dosage_kg"] + d_s), 2)
        form["ingredients"][2]["dosage_kg"] = round(max(0.1, form["ingredients"][2]["dosage_kg"] + d_st), 2)

        total = sum(it["dosage_kg"] for it in form["ingredients"] if it["ingredient_id"] != "WATER")
        for it in form["ingredients"]:
            if it["ingredient_id"] == "WATER":
                it["dosage_kg"] = round(max(0.0, 100.0 - total), 2)

        combo = combos[idx % max(1, len(combos))] if combos else {"strain_combo_id": "COMBO-TBD"}
        pred = None
        if model and model.get("ok"):
            sy, ov = predict(model, combo.get("strain_combo_id", ""), form, end_ph=4.6, ferm_time_h=8.0)
            pred = {"syneresis_pct": sy, "overall": ov}

        out.append({
            "candidate_id": f"C{idx+1}",
            "strain_combo_id": combo.get("strain_combo_id"),
            "formulation": form,
            "predicted": pred,
            "goals": goals
        })

    if model and model.get("ok"):
        out = sorted(out, key=lambda c: (c["predicted"]["overall"]*10 - c["predicted"]["syneresis_pct"]), reverse=True)
    return out

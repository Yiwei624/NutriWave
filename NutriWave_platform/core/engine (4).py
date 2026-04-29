from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import random

try:  # works both in the original package layout and in this uploaded flat layout
    from core.modeling import predict
except ModuleNotFoundError:  # pragma: no cover - local artifact convenience only
    from modeling import predict


@dataclass
class UserRequest:
    lang: str
    product_type: str
    base_id: str
    texture: str
    brief: str
    customer_profile: Optional[Dict[str, Any]] = None


# Texture words are not enough for a CMO. This table is the engineering translation layer:
# sensory target -> physical structure KPI -> factory-executable process window.
STRUCTURE_PROCESS_PRESETS: Dict[str, Dict[str, Any]] = {
    "soft": {
        "yield_stress_min_pa": 10.0,
        "viscosity_min_pa_s": 0.8,
        "syneresis_pct_max": 10.0,
        "overall_min": 4.0,
        "reference_stabilizer_kg": 0.30,
        "fermentation_temp_C": (37.0, 38.0),
        "fermentation_time_h": (7.0, 8.5),
        "max_shear_rpm": 80,
    },
    "thick": {
        "yield_stress_min_pa": 25.0,
        "viscosity_min_pa_s": 1.5,
        "syneresis_pct_max": 6.0,
        "overall_min": 4.0,
        "reference_stabilizer_kg": 0.45,
        # Deliberately narrow: this is the demo point for scale-up transfer.
        "fermentation_temp_C": (37.5, 38.2),
        "fermentation_time_h": (7.5, 9.0),
        "max_shear_rpm": 50,
    },
    "refreshing": {
        "yield_stress_min_pa": 5.0,
        "viscosity_min_pa_s": 0.35,
        "syneresis_pct_max": 12.0,
        "overall_min": 4.0,
        "reference_stabilizer_kg": 0.15,
        "fermentation_temp_C": (36.8, 37.8),
        "fermentation_time_h": (6.5, 8.0),
        "max_shear_rpm": 120,
    },
}


def _fmt_num(v: float) -> str:
    """Human-readable number for UI strings while preserving JSON numeric fields elsewhere."""
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:g}"


def _preset(texture: str) -> Dict[str, Any]:
    return STRUCTURE_PROCESS_PRESETS.get(texture, STRUCTURE_PROCESS_PRESETS["soft"])


def resolve_structure_kpi(texture: str, lang: str = "zh") -> Dict[str, Any]:
    """Translate a sensory texture word into measurable physical engineering KPIs.

    Example: thick -> yield stress > 25 Pa and viscosity > 1.5 Pa·s.
    This object is intentionally returned by the engine so the UI can show that
    NutriWave is selling a structure/process spec, not just a kitchen recipe.
    """
    p = _preset(texture)
    ys = float(p["yield_stress_min_pa"])
    visc = float(p["viscosity_min_pa_s"])
    sy = float(p["syneresis_pct_max"])

    summary_zh = (
        f"已解析结构 KPI：目标屈服应力 (Yield Stress) > {_fmt_num(ys)} Pa，"
        f"目标粘度 > {_fmt_num(visc)} Pa·s"
    )
    summary_en = (
        f"Parsed structure KPI: target yield stress > {_fmt_num(ys)} Pa; "
        f"target viscosity > {_fmt_num(visc)} Pa·s"
    )

    return {
        "texture_target": texture,
        "kpi_type": "structure_kpi",
        "yield_stress": {
            "name": "Yield Stress",
            "symbol": "τy",
            "operator": ">",
            "target_min": ys,
            "unit": "Pa",
            "display": f"> {_fmt_num(ys)} Pa",
        },
        "viscosity": {
            "name": "Rheological viscosity",
            "symbol": "η",
            "operator": ">",
            "target_min": visc,
            "unit": "Pa·s",
            "display": f"> {_fmt_num(visc)} Pa·s",
        },
        "syneresis": {
            "name": "Syneresis",
            "operator": "<=",
            "target_max": sy,
            "unit": "%",
            "display": f"≤ {_fmt_num(sy)}%",
        },
        "overall": {
            "name": "Overall sensory score",
            "operator": ">=",
            "target_min": float(p["overall_min"]),
            "unit": "1-5",
        },
        "measurement_hint": {
            "zh": "建议以 25°C 流变测试确认：表观粘度 η 与 vane/应力扫描屈服应力 τy。",
            "en": "Verify at 25°C by rheology: apparent viscosity η and vane/stress-sweep yield stress τy.",
        },
        "summary": {"zh": summary_zh, "en": summary_en},
        "summary_text": summary_zh if lang == "zh" else summary_en,
    }


def _form_dosages(formulation: Dict[str, Any]) -> Dict[str, float]:
    non_water = [
        it for it in (formulation or {}).get("ingredients", [])
        if it.get("ingredient_id") != "WATER"
    ]
    protein_kg = float(non_water[0].get("dosage_kg", 0.0)) if len(non_water) > 0 else 0.0
    sweetener_kg = float(non_water[1].get("dosage_kg", 0.0)) if len(non_water) > 1 else 0.0
    stabilizer_kg = float(non_water[2].get("dosage_kg", 0.0)) if len(non_water) > 2 else 0.0
    return {"protein_kg": protein_kg, "sweetener_kg": sweetener_kg, "stabilizer_kg": stabilizer_kg}


def estimate_physical_kpis(
    texture: str,
    formulation: Dict[str, Any],
    predicted: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Lightweight surrogate layer for physical KPIs.

    When a trained Row5 model exists, sensory/syneresis prediction still comes from that model.
    This function adds the missing engineering layer: approximate yield stress and viscosity
    from the same candidate formulation so the UI can speak in plant/process-control terms.
    """
    p = _preset(texture)
    d = _form_dosages(formulation)
    stabilizer_delta = d["stabilizer_kg"] - float(p["reference_stabilizer_kg"])
    protein_delta = d["protein_kg"] - 8.0

    yield_min = float(p["yield_stress_min_pa"])
    viscosity_min = float(p["viscosity_min_pa_s"])

    # Conservative deterministic estimates: enough to make the prototype demo factory physics
    # without pretending to be a validated mechanistic model.
    yield_stress_pa = yield_min + 2.5 + 18.0 * stabilizer_delta + 0.10 * protein_delta
    viscosity_pa_s = viscosity_min + 0.12 + 0.90 * stabilizer_delta + 0.015 * protein_delta

    # If the trained surrogate predicts high syneresis, show some structural risk instead of
    # blindly declaring a pass. This keeps the demo more credible.
    sy_pred = None if not predicted else predicted.get("syneresis_pct")
    if sy_pred is not None and sy_pred > float(p["syneresis_pct_max"]):
        yield_stress_pa -= 1.5
        viscosity_pa_s -= 0.08

    yield_stress_pa = max(0.0, yield_stress_pa)
    viscosity_pa_s = max(0.0, viscosity_pa_s)

    pass_structure = yield_stress_pa > yield_min and viscosity_pa_s > viscosity_min
    return {
        "yield_stress_Pa": round(yield_stress_pa, 1),
        "rheological_viscosity_Pa_s": round(viscosity_pa_s, 2),
        "syneresis_pct_max": float(p["syneresis_pct_max"]),
        "status": "predicted_pass" if pass_structure else "risk_review",
        "interpretation": (
            "structure KPI likely passes; validate with rheometer before CMO transfer"
            if pass_structure else
            "structure KPI risk; widen DoE or increase stabilizer/EPS contribution before scale-up"
        ),
    }


def build_process_window(
    texture: str,
    base_id: str,
    formulation: Dict[str, Any],
    physical_kpis: Dict[str, Any],
    predicted: Optional[Dict[str, Any]] = None,
    model: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return the factory-facing process window and QC gates.

    This is now the core deliverable. The JSON formulation remains as an audit trail.
    """
    p = _preset(texture)
    temp_min, temp_max = p["fermentation_temp_C"]
    time_min, time_max = p["fermentation_time_h"]
    ys = float(p["yield_stress_min_pa"])
    visc = float(p["viscosity_min_pa_s"])
    sy = float(p["syneresis_pct_max"])
    rpm = int(p["max_shear_rpm"])

    trained = bool(model and model.get("ok"))
    model_source = "trained_surrogate_v1_plus_physics_window" if trained else "physics_seed_surrogate_window_v1"

    qc_stop_zh = (
        f"pH 达到 4.6 且 流变粘度达到 {_fmt_num(visc)} Pa·s：立即停止发酵，降温至 4°C；"
        f"后搅拌不得超过 {rpm} RPM。"
    )
    qc_stop_en = (
        f"Stop fermentation immediately when pH reaches 4.6 and rheological viscosity reaches "
        f"{_fmt_num(visc)} Pa·s; cool to 4°C; post-stir must not exceed {rpm} RPM."
    )

    return {
        "window_id": f"PW-{texture.upper()}-{base_id.upper()}-v1",
        "core_deliverable": "process_window",
        "basis": "factory_executable_starting_window_per_100kg",
        "surrogate_model_source": model_source,
        "fermentation_temperature_C": {
            "min": float(temp_min),
            "max": float(temp_max),
            "display": f"{_fmt_num(temp_min)}°C - {_fmt_num(temp_max)}°C",
        },
        "fermentation_time_h": {
            "min": float(time_min),
            "max": float(time_max),
            "control_note": "Secondary control only; final stop is QC-gated by pH + rheology.",
        },
        "maximum_shear": {
            "post_fermentation_stir_rpm_max": rpm,
            "display": f"≤ {rpm} RPM",
            "rationale": "Avoid shear collapse of EPS/protein gel network during scale-up transfer.",
        },
        "qc_gates": {
            "fermentation_stop": {
                "pH_end": {"operator": "<=", "target": 4.6, "unit": "pH"},
                "rheological_viscosity_Pa_s": {"operator": ">=", "target": visc, "unit": "Pa·s"},
                "action": "stop_fermentation_immediately_and_cool_to_4C",
            },
            "structure_release": {
                "yield_stress_Pa": {"operator": ">=", "target": ys, "unit": "Pa"},
                "rheological_viscosity_Pa_s": {"operator": ">=", "target": visc, "unit": "Pa·s"},
                "syneresis_pct": {"operator": "<=", "target": sy, "unit": "%"},
            },
        },
        "predicted_physical_kpis": physical_kpis,
        "predicted_sensory_and_stability": predicted,
        "display": {
            "zh": {
                "fermentation_temperature_C": f"{_fmt_num(temp_min)}°C - {_fmt_num(temp_max)}°C",
                "max_shear_rpm": f"{rpm} RPM",
                "qc_stop_condition": qc_stop_zh,
                "structure_release": f"τy ≥ {_fmt_num(ys)} Pa；η ≥ {_fmt_num(visc)} Pa·s；析水率 ≤ {_fmt_num(sy)}%",
            },
            "en": {
                "fermentation_temperature_C": f"{_fmt_num(temp_min)}°C - {_fmt_num(temp_max)}°C",
                "max_shear_rpm": f"{rpm} RPM",
                "qc_stop_condition": qc_stop_en,
                "structure_release": f"τy ≥ {_fmt_num(ys)} Pa; η ≥ {_fmt_num(visc)} Pa·s; syneresis ≤ {_fmt_num(sy)}%",
            },
        },
    }


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


def choose_default_formulation(
    data: Dict[str, Any],
    base_id: str,
    texture: str,
    customer_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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
        "version": "process_structure_co_engine_v2",
        "ingredients": [
            {"ingredient_id": (protein or {}).get("ingredient_id", "TBD"), "dosage_kg": round(protein_kg, 2)},
            {"ingredient_id": (sweet or {}).get("ingredient_id", "TBD"), "dosage_kg": round(sweet_kg, 2)},
            {"ingredient_id": (stab or {}).get("ingredient_id", "TBD"), "dosage_kg": round(stab_kg, 2)},
            {"ingredient_id": "WATER", "dosage_kg": round(water, 2)},
        ],
    }


def generate_candidates(
    data: Dict[str, Any],
    req: UserRequest,
    model: Optional[Dict[str, Any]] = None,
    k: int = 3,
) -> List[Dict[str, Any]]:
    base_form = choose_default_formulation(data, req.base_id, req.texture, req.customer_profile)
    goals = infer_goals(req.brief, req.texture)
    structure_kpi = resolve_structure_kpi(req.texture, req.lang)

    grid = [(-0.05, 0.0), (0.0, 0.0), (0.05, 0.0), (0.0, -0.05), (0.0, 0.05)]
    random.seed(42)
    random.shuffle(grid)

    combos = sorted(
        data.get("strains", []),
        key=lambda c: sum(2 for g in goals if g in set(c.get("benefit_tags", []))),
        reverse=True,
    ) or []

    out = []
    for idx in range(k):
        d_s, d_st = grid[idx % len(grid)]
        form = {
            "base_id": base_form["base_id"],
            "basis": base_form["basis"],
            "version": base_form["version"],
            "role": "formulation_audit_trail_not_core_deliverable",
            "ingredients": [dict(x) for x in base_form["ingredients"]],
        }

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

        physical_kpis = estimate_physical_kpis(req.texture, form, pred)
        process_window = build_process_window(
            texture=req.texture,
            base_id=req.base_id,
            formulation=form,
            physical_kpis=physical_kpis,
            predicted=pred,
            model=model,
        )

        out.append(
            {
                "candidate_id": f"C{idx+1}",
                "core_deliverable": "process_window",
                "strain_combo_id": combo.get("strain_combo_id"),
                "structure_kpi": structure_kpi,
                "process_window": process_window,
                "predicted_physical_kpis": physical_kpis,
                "formulation": form,
                "predicted": pred,
                "goals": goals,
            }
        )

    if model and model.get("ok"):
        out = sorted(out, key=lambda c: (c["predicted"]["overall"] * 10 - c["predicted"]["syneresis_pct"]), reverse=True)
    return out

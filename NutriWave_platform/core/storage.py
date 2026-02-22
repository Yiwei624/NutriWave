from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "data.json"

STRAINS_PATH = ROOT / "data" / "strains.jsonl"
ING_PATH = ROOT / "data" / "ingredients.jsonl"
RHEO_PATH = ROOT / "data" / "rheo_methods.jsonl"
FORM_PATH = ROOT / "data" / "formulations.jsonl"
RUNS_PATH = ROOT / "data" / "runs.jsonl"
MODELS_PATH = ROOT / "data" / "models.jsonl"

def _read_jsonl(path: Path, limit: int = 5000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out[-limit:]

def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = dict(record)
    rec.setdefault("timestamp_utc", datetime.utcnow().isoformat())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _merge_by_id(seed_list: List[Dict[str, Any]], overlay_list: List[Dict[str, Any]], id_key: str) -> List[Dict[str, Any]]:
    overlay_map = {x.get(id_key): x for x in overlay_list if x.get(id_key) is not None}
    merged: List[Dict[str, Any]] = []
    seen = set()
    for x in seed_list:
        _id = x.get(id_key)
        if _id is None:
            continue
        merged.append(overlay_map.get(_id, x))
        seen.add(_id)
    for _id, x in overlay_map.items():
        if _id not in seen:
            merged.append(x)
            seen.add(_id)
    return merged

def load_data() -> Dict[str, Any]:
    with DATA_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    strains_ov = _read_jsonl(STRAINS_PATH)
    ing_ov = _read_jsonl(ING_PATH)
    rheo_ov = _read_jsonl(RHEO_PATH)
    form_ov = _read_jsonl(FORM_PATH)

    # strains overlay: split by kind (strain vs combo)
    seed_strains = data.get("strains", [])
    seed_str = [s for s in seed_strains if s.get("kind") != "combo"]
    seed_cmb = [s for s in seed_strains if s.get("kind") == "combo"]
    ov_str = [s for s in strains_ov if s.get("kind") != "combo" and s.get("strain_combo_id") is None]
    ov_cmb = [s for s in strains_ov if s.get("kind") == "combo" or s.get("strain_combo_id") is not None]
    data["strains"] = _merge_by_id(seed_str, ov_str, "strain_id") + _merge_by_id(seed_cmb, ov_cmb, "strain_combo_id")

    data["ingredients"] = _merge_by_id(data.get("ingredients", []), ing_ov, "ingredient_id")
    data["rheo_methods"] = _merge_by_id(data.get("rheo_methods", []), rheo_ov, "rheo_method_id")
    data["formulations"] = _merge_by_id(data.get("formulations", []), form_ov, "formulation_id")
    return data

# append APIs
def append_strain(record: Dict[str, Any]) -> None:
    _append_jsonl(STRAINS_PATH, record)

def append_ingredient(record: Dict[str, Any]) -> None:
    _append_jsonl(ING_PATH, record)

def append_rheo_method(record: Dict[str, Any]) -> None:
    _append_jsonl(RHEO_PATH, record)

def append_formulation(record: Dict[str, Any]) -> None:
    _append_jsonl(FORM_PATH, record)

def append_run(record: Dict[str, Any]) -> None:
    _append_jsonl(RUNS_PATH, record)

def append_model(record: Dict[str, Any]) -> None:
    _append_jsonl(MODELS_PATH, record)

# iter APIs
def iter_runs(limit: int = 5000) -> List[Dict[str, Any]]:
    return _read_jsonl(RUNS_PATH, limit)

def iter_models(limit: int = 2000) -> List[Dict[str, Any]]:
    return _read_jsonl(MODELS_PATH, limit)

# Row5A learning scores
def compute_learning_scores(data: Dict[str, Any], product_type: str, texture: str) -> Dict[str, Any]:
    runs = iter_runs(limit=5000)
    if not runs:
        return {"strain_combo_scores": {}, "ingredient_scores": {}, "formulation_scores": {}, "n_used": 0}

    methods = {m.get("rheo_method_id"): m for m in data.get("rheo_methods", [])}
    targets = data.get("targets", {}).get(texture, {}).get("en", {})
    sy_max = targets.get("syneresis_pct_max", 10)

    def is_valid(run: Dict[str, Any]) -> bool:
        if run.get("product_type") != product_type or run.get("texture") != texture:
            return False
        m = methods.get(run.get("rheo_method_id"), {})
        gates = m.get("quality_gates", {}) or {}
        rheo = run.get("rheology", {}) or {}
        q = run.get("quality_flags", {}) or {}
        if gates.get("require_full_regime", False):
            if rheo.get("regime") not in ["full (Λ≥1)", "full"]:
                return False
        if gates.get("require_torque_floor_ok", False) and (q.get("torque_floor_ok") is False):
            return False
        if gates.get("require_repeatability_ok", False) and (q.get("repeatability_ok") is False):
            return False
        return True

    def is_pass(run: Dict[str, Any]) -> bool:
        sy = (run.get("rheology", {}) or {}).get("syneresis_pct")
        ov = (run.get("sensory", {}) or {}).get("overall")
        if sy is None or ov is None:
            return False
        return float(sy) <= float(sy_max) and int(ov) >= 4

    used = [r for r in runs if is_valid(r)]
    if not used:
        return {"strain_combo_scores": {}, "ingredient_scores": {}, "formulation_scores": {}, "n_used": 0}

    def upd(store: Dict[str, Any], key: str, passed: bool, overall: Optional[int]):
        if not key:
            return
        s = store.setdefault(key, {"n": 0, "pass": 0, "overall_sum": 0})
        s["n"] += 1
        s["pass"] += 1 if passed else 0
        if overall is not None:
            s["overall_sum"] += int(overall)

    strain_scores: Dict[str, Any] = {}
    ing_scores: Dict[str, Any] = {}
    form_scores: Dict[str, Any] = {}

    for r in used:
        p = is_pass(r)
        ov = (r.get("sensory", {}) or {}).get("overall")
        upd(strain_scores, r.get("strain_combo_id") or r.get("strain_id"), p, ov)
        for iid in (r.get("ingredient_ids") or []):
            upd(ing_scores, iid, p, ov)
        upd(form_scores, r.get("formulation_id"), p, ov)

    def finalize(store: Dict[str, Any]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for k, v in store.items():
            n = v["n"]
            pass_rate = v["pass"]/n if n else 0.0
            ov_mean = v["overall_sum"]/n if n else 0.0
            out[k] = round(100.0*pass_rate + 5.0*ov_mean, 3)
        return out

    return {
        "strain_combo_scores": finalize(strain_scores),
        "ingredient_scores": finalize(ing_scores),
        "formulation_scores": finalize(form_scores),
        "n_used": len(used),
        "syneresis_threshold": sy_max
    }

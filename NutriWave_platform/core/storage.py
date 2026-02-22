\
from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "data.json"

# append-only jsonl (supports edit + delete via tombstone)
P_STR = ROOT / "data" / "strains.jsonl"
P_ING = ROOT / "data" / "ingredients.jsonl"
P_RHEO = ROOT / "data" / "rheo_methods.jsonl"
P_SUP = ROOT / "data" / "suppliers.jsonl"
P_FORM = ROOT / "data" / "formulations.jsonl"
P_RUN = ROOT / "data" / "runs.jsonl"
P_MODEL = ROOT / "data" / "models.jsonl"

def _read_jsonl(path: Path, limit: int = 10000) -> List[Dict[str, Any]]:
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

def _latest_by_id(records: List[Dict[str, Any]], id_key: str) -> Dict[str, Dict[str, Any]]:
    m: Dict[str, Dict[str, Any]] = {}
    for r in records:
        _id = r.get(id_key)
        if _id is None:
            continue
        m[_id] = r  # later overrides earlier
    return {k:v for k,v in m.items() if not v.get("is_deleted", False)}

def _merge(seed_list: List[Dict[str, Any]], overlay: List[Dict[str, Any]], id_key: str) -> List[Dict[str, Any]]:
    o = _latest_by_id(overlay, id_key)
    out: List[Dict[str, Any]] = []
    seen = set()
    for s in seed_list:
        sid = s.get(id_key)
        if sid is None:
            continue
        out.append(o.get(sid, s))
        seen.add(sid)
    for sid, rec in o.items():
        if sid not in seen:
            out.append(rec)
    return out

def load_data() -> Dict[str, Any]:
    with DATA_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    ov_str = _read_jsonl(P_STR)
    ov_ing = _read_jsonl(P_ING)
    ov_rheo = _read_jsonl(P_RHEO)
    ov_sup = _read_jsonl(P_SUP)
    ov_form = _read_jsonl(P_FORM)

    seed_combo = [x for x in data.get("strains", []) if x.get("kind") == "combo"]
    ov_combo = [x for x in ov_str if x.get("kind") == "combo" or x.get("strain_combo_id") is not None]
    data["strains"] = _merge(seed_combo, ov_combo, "strain_combo_id")

    data["ingredients"] = _merge(data.get("ingredients", []), ov_ing, "ingredient_id")
    data["rheo_methods"] = _merge(data.get("rheo_methods", []), ov_rheo, "rheo_method_id")
    data["suppliers"] = _merge(data.get("suppliers", []), ov_sup, "supplier_id")
    data["formulations"] = _merge(data.get("formulations", []), ov_form, "formulation_id")
    return data

# CRUD: upsert/delete (tombstone)
def upsert_strain_combo(rec: Dict[str, Any]) -> None:
    rec = dict(rec); rec["kind"] = "combo"
    _append_jsonl(P_STR, rec)

def delete_strain_combo(strain_combo_id: str) -> None:
    _append_jsonl(P_STR, {"kind":"combo","strain_combo_id": strain_combo_id, "is_deleted": True})

def upsert_ingredient(rec: Dict[str, Any]) -> None:
    _append_jsonl(P_ING, rec)

def delete_ingredient(ingredient_id: str) -> None:
    _append_jsonl(P_ING, {"ingredient_id": ingredient_id, "is_deleted": True})

def upsert_rheo_method(rec: Dict[str, Any]) -> None:
    _append_jsonl(P_RHEO, rec)

def delete_rheo_method(rheo_method_id: str) -> None:
    _append_jsonl(P_RHEO, {"rheo_method_id": rheo_method_id, "is_deleted": True})

def upsert_supplier(rec: Dict[str, Any]) -> None:
    _append_jsonl(P_SUP, rec)

def delete_supplier(supplier_id: str) -> None:
    _append_jsonl(P_SUP, {"supplier_id": supplier_id, "is_deleted": True})

def upsert_formulation(rec: Dict[str, Any]) -> None:
    _append_jsonl(P_FORM, rec)

def delete_formulation(formulation_id: str) -> None:
    _append_jsonl(P_FORM, {"formulation_id": formulation_id, "is_deleted": True})

def append_run(rec: Dict[str, Any]) -> None:
    _append_jsonl(P_RUN, rec)

def iter_runs(limit: int = 10000) -> List[Dict[str, Any]]:
    return _read_jsonl(P_RUN, limit)

def append_model(rec: Dict[str, Any]) -> None:
    _append_jsonl(P_MODEL, rec)

def iter_models(limit: int = 2000) -> List[Dict[str, Any]]:
    return _read_jsonl(P_MODEL, limit)

def get_latest_model(model_type: str = "surrogate_v1") -> Optional[Dict[str, Any]]:
    latest = None
    for m in iter_models(limit=5000):
        if m.get("model_type") == model_type and not m.get("is_deleted", False):
            latest = m
    return latest

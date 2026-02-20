from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "data.json"

STRANDS_PATH = ROOT / "data" / "strains.jsonl"
ING_PATH = ROOT / "data" / "ingredients.jsonl"
RHEO_PATH = ROOT / "data" / "rheo_methods.jsonl"
RUNS_PATH = ROOT / "data" / "runs.jsonl"
MODELS_PATH = ROOT / "data" / "models.jsonl"

def _read_jsonl(path: Path, limit: int = 2000) -> List[Dict[str, Any]]:
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
    # overlay wins by id_key; keep insertion order: seed then new overlay-only at end
    seed_map = {x.get(id_key): x for x in seed_list if x.get(id_key) is not None}
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

    # Overlays
    strains_ov = _read_jsonl(STRANDS_PATH)
    ing_ov = _read_jsonl(ING_PATH)
    rheo_ov = _read_jsonl(RHEO_PATH)

    data["strains"] = _merge_by_id(data.get("strains", []), strains_ov, "strain_id")
    data["ingredients"] = _merge_by_id(data.get("ingredients", []), ing_ov, "ingredient_id")
    data["rheo_methods"] = _merge_by_id(data.get("rheo_methods", []), rheo_ov, "rheo_method_id")
    return data

# --- Admin write APIs (local jsonl) ---
def append_strain(record: Dict[str, Any]) -> None:
    _append_jsonl(STRANDS_PATH, record)

def append_ingredient(record: Dict[str, Any]) -> None:
    _append_jsonl(ING_PATH, record)

def append_rheo_method(record: Dict[str, Any]) -> None:
    _append_jsonl(RHEO_PATH, record)

def append_run(record: Dict[str, Any]) -> None:
    _append_jsonl(RUNS_PATH, record)

def append_model(record: Dict[str, Any]) -> None:
    _append_jsonl(MODELS_PATH, record)

# --- Admin read APIs ---
def iter_strains(limit: int = 2000) -> List[Dict[str, Any]]:
    return _read_jsonl(STRANDS_PATH, limit)

def iter_ingredients(limit: int = 2000) -> List[Dict[str, Any]]:
    return _read_jsonl(ING_PATH, limit)

def iter_rheo_methods(limit: int = 2000) -> List[Dict[str, Any]]:
    return _read_jsonl(RHEO_PATH, limit)

def iter_runs(limit: int = 2000) -> List[Dict[str, Any]]:
    return _read_jsonl(RUNS_PATH, limit)

def iter_models(limit: int = 2000) -> List[Dict[str, Any]]:
    return _read_jsonl(MODELS_PATH, limit)

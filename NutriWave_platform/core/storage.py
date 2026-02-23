from __future__ import annotations

from pathlib import Path
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


# -----------------------------
# Storage layout
# -----------------------------

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "data.json"
if not DATA_PATH.exists():
    # fallback for dev layouts
    alt = ROOT / "data.json"
    if alt.exists():
        DATA_PATH = alt

# Legacy append-only jsonl (supports edit + delete via tombstone)
P_STR = ROOT / "data" / "strains.jsonl"
P_ING = ROOT / "data" / "ingredients.jsonl"
P_RHEO = ROOT / "data" / "rheo_methods.jsonl"
P_SUP = ROOT / "data" / "suppliers.jsonl"
P_FORM = ROOT / "data" / "formulations.jsonl"
P_RUN = ROOT / "data" / "runs.jsonl"
P_MODEL = ROOT / "data" / "models.jsonl"

# New Admin Database (Row1–Row6 redesigned)
P2_SUPPLIERS = ROOT / "data" / "admin_suppliers.jsonl"
P2_CONTACTS = ROOT / "data" / "admin_supplier_contacts.jsonl"
P2_MATERIALS = ROOT / "data" / "admin_materials.jsonl"
P2_SUPPLIER_MATERIALS = ROOT / "data" / "admin_supplier_materials.jsonl"
P2_STRAIN_PRODUCTS = ROOT / "data" / "admin_strain_products.jsonl"
P2_STRAIN_COMPONENTS = ROOT / "data" / "admin_strain_components.jsonl"
P2_MATERIAL_LOTS = ROOT / "data" / "admin_material_lots.jsonl"
P2_RHEO_SETUPS = ROOT / "data" / "admin_rheo_setups.jsonl"
P2_FORMULATIONS = ROOT / "data" / "admin_formulations.jsonl"
P2_FORM_LINES = ROOT / "data" / "admin_formulation_lines.jsonl"
P2_PROCESSES = ROOT / "data" / "admin_processes.jsonl"
P2_RUNS = ROOT / "data" / "admin_runs.jsonl"
P2_RESULTS = ROOT / "data" / "admin_run_results.jsonl"
P2_MODEL_RUNS = ROOT / "data" / "admin_model_runs.jsonl"
P2_MODEL_PRED = ROOT / "data" / "admin_model_predictions.jsonl"


# -----------------------------
# JSONL helpers
# -----------------------------

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
        m[str(_id)] = r
    return {k: v for k, v in m.items() if not v.get("is_deleted", False)}


def _merge(seed_list: List[Dict[str, Any]], overlay: List[Dict[str, Any]], id_key: str) -> List[Dict[str, Any]]:
    o = _latest_by_id(overlay, id_key)
    out: List[Dict[str, Any]] = []
    seen = set()
    for s in seed_list:
        sid = s.get(id_key)
        if sid is None:
            continue
        sid = str(sid)
        out.append(o.get(sid, s))
        seen.add(sid)
    for sid, rec in o.items():
        if sid not in seen:
            out.append(rec)
    return out


# -----------------------------
# Legacy data loader (unchanged behavior)
# -----------------------------

def load_data() -> Dict[str, Any]:
    """Loads the legacy seed data.json and merges legacy overlay jsonl files.

    NOTE: This is intentionally kept stable so the Recipe Engine remains unchanged.
    The new Admin Database is loaded via load_admin_db().
    """
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


# -----------------------------
# Legacy CRUD (unchanged)
# -----------------------------

def upsert_strain_combo(rec: Dict[str, Any]) -> None:
    rec = dict(rec)
    rec["kind"] = "combo"
    _append_jsonl(P_STR, rec)


def delete_strain_combo(strain_combo_id: str) -> None:
    _append_jsonl(P_STR, {"kind": "combo", "strain_combo_id": strain_combo_id, "is_deleted": True})


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


# -----------------------------
# New Admin DB helpers
# -----------------------------

def _composite_id(*parts: Any) -> str:
    return "|".join([str(p).strip() for p in parts])


def _load_table(path: Path, id_key: str, limit: int = 20000) -> List[Dict[str, Any]]:
    records = _read_jsonl(path, limit=limit)
    latest = _latest_by_id(records, id_key)
    return list(latest.values())


def load_admin_db() -> Dict[str, Any]:
    """Load the redesigned Admin Database (Row1–Row6).

    This does NOT affect the recipe engine.
    """
    return {
        "suppliers2": _load_table(P2_SUPPLIERS, "supplier_company_id"),
        "supplier_contacts": _load_table(P2_CONTACTS, "contact_id"),
        "materials2": _load_table(P2_MATERIALS, "material_id"),
        "supplier_materials": _load_table(P2_SUPPLIER_MATERIALS, "supplier_material_id"),
        "strain_products": _load_table(P2_STRAIN_PRODUCTS, "strain_product_id"),
        "strain_components": _load_table(P2_STRAIN_COMPONENTS, "strain_component_id"),
        "material_lots": _load_table(P2_MATERIAL_LOTS, "lot_id"),
        "rheo_setups": _load_table(P2_RHEO_SETUPS, "rheo_setup_id"),
        "formulations2": _load_table(P2_FORMULATIONS, "formulation_id"),
        "formulation_lines": _load_table(P2_FORM_LINES, "line_id"),
        "processes": _load_table(P2_PROCESSES, "process_id"),
        "runs2": _load_table(P2_RUNS, "run_id"),
        "run_results": _load_table(P2_RESULTS, "run_id"),
        "model_runs": _load_table(P2_MODEL_RUNS, "model_run_id"),
        "model_predictions": _load_table(P2_MODEL_PRED, "prediction_id"),
    }


# Generic upsert/delete for admin tables

def admin_upsert(path: Path, id_key: str, rec: Dict[str, Any]) -> None:
    if id_key not in rec or not rec.get(id_key):
        raise ValueError(f"Missing primary key: {id_key}")
    _append_jsonl(path, rec)


def admin_delete(path: Path, id_key: str, _id: str) -> None:
    _append_jsonl(path, {id_key: _id, "is_deleted": True})


# Suppliers
def upsert_supplier2(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_SUPPLIERS, "supplier_company_id", rec)


def delete_supplier2(supplier_company_id: str) -> None:
    admin_delete(P2_SUPPLIERS, "supplier_company_id", supplier_company_id)


def upsert_supplier_contact(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_CONTACTS, "contact_id", rec)


def delete_supplier_contact(contact_id: str) -> None:
    admin_delete(P2_CONTACTS, "contact_id", contact_id)


# Materials
def upsert_material2(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_MATERIALS, "material_id", rec)


def delete_material2(material_id: str) -> None:
    admin_delete(P2_MATERIALS, "material_id", material_id)


def upsert_supplier_material(rec: Dict[str, Any]) -> None:
    # enforce composite key
    if not rec.get("supplier_material_id"):
        rec = dict(rec)
        rec["supplier_material_id"] = _composite_id(rec.get("supplier_company_id"), rec.get("material_id"))
    admin_upsert(P2_SUPPLIER_MATERIALS, "supplier_material_id", rec)


def delete_supplier_material(supplier_material_id: str) -> None:
    admin_delete(P2_SUPPLIER_MATERIALS, "supplier_material_id", supplier_material_id)


# Strain products
def upsert_strain_product(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_STRAIN_PRODUCTS, "strain_product_id", rec)


def delete_strain_product(strain_product_id: str) -> None:
    admin_delete(P2_STRAIN_PRODUCTS, "strain_product_id", strain_product_id)


def upsert_strain_component(rec: Dict[str, Any]) -> None:
    if not rec.get("strain_component_id"):
        rec = dict(rec)
        rec["strain_component_id"] = _composite_id(rec.get("strain_product_id"), rec.get("component_name"))
    admin_upsert(P2_STRAIN_COMPONENTS, "strain_component_id", rec)


def delete_strain_component(strain_component_id: str) -> None:
    admin_delete(P2_STRAIN_COMPONENTS, "strain_component_id", strain_component_id)


# Lots
def upsert_material_lot(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_MATERIAL_LOTS, "lot_id", rec)


def delete_material_lot(lot_id: str) -> None:
    admin_delete(P2_MATERIAL_LOTS, "lot_id", lot_id)


# Rheology setups
def upsert_rheo_setup(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_RHEO_SETUPS, "rheo_setup_id", rec)


def delete_rheo_setup(rheo_setup_id: str) -> None:
    admin_delete(P2_RHEO_SETUPS, "rheo_setup_id", rheo_setup_id)


# Formulations (header + lines)
def upsert_formulation2(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_FORMULATIONS, "formulation_id", rec)


def delete_formulation2(formulation_id: str) -> None:
    admin_delete(P2_FORMULATIONS, "formulation_id", formulation_id)


def upsert_formulation_line(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_FORM_LINES, "line_id", rec)


def delete_formulation_line(line_id: str) -> None:
    admin_delete(P2_FORM_LINES, "line_id", line_id)


# Processes / Runs / Results
def upsert_process(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_PROCESSES, "process_id", rec)


def delete_process(process_id: str) -> None:
    admin_delete(P2_PROCESSES, "process_id", process_id)


def upsert_run2(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_RUNS, "run_id", rec)


def delete_run2(run_id: str) -> None:
    admin_delete(P2_RUNS, "run_id", run_id)


def upsert_run_result(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_RESULTS, "run_id", rec)


def delete_run_result(run_id: str) -> None:
    admin_delete(P2_RESULTS, "run_id", run_id)


# Models (Row6)
def upsert_model_run(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_MODEL_RUNS, "model_run_id", rec)


def delete_model_run(model_run_id: str) -> None:
    admin_delete(P2_MODEL_RUNS, "model_run_id", model_run_id)


def upsert_model_prediction(rec: Dict[str, Any]) -> None:
    admin_upsert(P2_MODEL_PRED, "prediction_id", rec)


def delete_model_prediction(prediction_id: str) -> None:
    admin_delete(P2_MODEL_PRED, "prediction_id", prediction_id)


# Convenience: upload parsing helpers (used in app)

def normalize_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    return {str(k).strip(): v for k, v in d.items()}


def map_columns(row: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    """Map both zh/en headers to canonical field names."""
    out: Dict[str, Any] = {}
    for k, v in row.items():
        kk = str(k).strip()
        canon = mapping.get(kk)
        if canon:
            out[canon] = v
        else:
            # keep unknown fields as extras
            out.setdefault("extra", {})[kk] = v
    # remove empty extras
    if out.get("extra") == {}:
        out.pop("extra", None)
    return out


def get_admin_paths() -> Dict[str, Tuple[Path, str]]:
    """Return table name -> (jsonl path, primary key)."""
    return {
        "suppliers2": (P2_SUPPLIERS, "supplier_company_id"),
        "supplier_contacts": (P2_CONTACTS, "contact_id"),
        "materials2": (P2_MATERIALS, "material_id"),
        "supplier_materials": (P2_SUPPLIER_MATERIALS, "supplier_material_id"),
        "strain_products": (P2_STRAIN_PRODUCTS, "strain_product_id"),
        "strain_components": (P2_STRAIN_COMPONENTS, "strain_component_id"),
        "material_lots": (P2_MATERIAL_LOTS, "lot_id"),
        "rheo_setups": (P2_RHEO_SETUPS, "rheo_setup_id"),
        "formulations2": (P2_FORMULATIONS, "formulation_id"),
        "formulation_lines": (P2_FORM_LINES, "line_id"),
        "processes": (P2_PROCESSES, "process_id"),
        "runs2": (P2_RUNS, "run_id"),
        "run_results": (P2_RESULTS, "run_id"),
        "model_runs": (P2_MODEL_RUNS, "model_run_id"),
        "model_predictions": (P2_MODEL_PRED, "prediction_id"),
    }

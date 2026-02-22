\
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import numpy as np

def _one_hot_index(values: List[str]) -> Dict[str, int]:
    return {v:i for i,v in enumerate(sorted(set(values)))}

def build_training_matrix(runs: List[Dict[str, Any]], gate_full: bool = True) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
    usable = []
    for r in runs:
        rheo = r.get("rheology", {}) or {}
        q = r.get("quality_flags", {}) or {}
        if gate_full:
            if rheo.get("regime") not in ["full (Λ≥1)", "full"]:
                continue
            if q.get("torque_floor_ok") is False:
                continue
        sy = rheo.get("syneresis_pct")
        ov = (r.get("sensory", {}) or {}).get("overall")
        if sy is None or ov is None:
            continue
        if (r.get("formulation") or {}).get("ingredients") is None:
            continue
        usable.append(r)

    if len(usable) < 8:
        return np.zeros((0,1)), np.zeros((0,)), np.zeros((0,)), {"n_used": len(usable), "reason": "too_few_runs"}

    combo_ids = [r.get("strain_combo_id","") for r in usable]
    combo_index = _one_hot_index(combo_ids)

    ing_ids = []
    for r in usable:
        for it in (r.get("formulation") or {}).get("ingredients", []):
            iid = it.get("ingredient_id")
            if iid and iid != "WATER":
                ing_ids.append(iid)
    ing_index = _one_hot_index(ing_ids) if ing_ids else {}

    n = len(usable)
    p = len(combo_index) + len(ing_index) + 2  # end_ph, ferm_time
    X = np.zeros((n, p), dtype=float)
    y_sy = np.zeros((n,), dtype=float)
    y_ov = np.zeros((n,), dtype=float)

    for i, r in enumerate(usable):
        c = r.get("strain_combo_id","")
        if c in combo_index:
            X[i, combo_index[c]] = 1.0

        offset = len(combo_index)
        for it in (r.get("formulation") or {}).get("ingredients", []):
            iid = it.get("ingredient_id")
            if not iid or iid == "WATER":
                continue
            j = ing_index.get(iid)
            if j is not None:
                X[i, offset + j] = float(it.get("dosage_kg", 0.0))

        X[i, offset + len(ing_index) + 0] = float(r.get("end_ph", 0.0))
        X[i, offset + len(ing_index) + 1] = float(r.get("fermentation_time_h", 0.0))

        y_sy[i] = float((r.get("rheology") or {}).get("syneresis_pct"))
        y_ov[i] = float((r.get("sensory") or {}).get("overall"))

    schema = {"combo_index": combo_index, "ingredient_index": ing_index, "n_used": n}
    return X, y_sy, y_ov, schema

def ridge_fit(X: np.ndarray, y: np.ndarray, alpha: float = 1.0):
    p = X.shape[1]
    w = np.linalg.solve(X.T@X + alpha*np.eye(p), X.T@y)
    rmse = float(np.sqrt(np.mean((y - X@w)**2)))
    return w, rmse

def train_surrogate(runs: List[Dict[str, Any]], alpha: float = 1.0, gate_full: bool = True) -> Dict[str, Any]:
    X, y_sy, y_ov, schema = build_training_matrix(runs, gate_full=gate_full)
    if X.shape[0] == 0:
        return {"ok": False, "schema": schema}
    w_sy, rmse_sy = ridge_fit(X, y_sy, alpha=alpha)
    w_ov, rmse_ov = ridge_fit(X, y_ov, alpha=alpha)
    return {
        "ok": True,
        "schema": schema,
        "alpha": alpha,
        "gate_full": gate_full,
        "weights_syneresis": w_sy.tolist(),
        "weights_overall": w_ov.tolist(),
        "rmse_syneresis": rmse_sy,
        "rmse_overall": rmse_ov
    }

def predict(model: Dict[str, Any], combo_id: str, formulation: Dict[str, Any], end_ph: float, ferm_time_h: float):
    schema = model["schema"]
    combo_index = schema["combo_index"]
    ing_index = schema["ingredient_index"]
    p = len(combo_index) + len(ing_index) + 2
    x = np.zeros((p,), dtype=float)

    if combo_id in combo_index:
        x[combo_index[combo_id]] = 1.0

    offset = len(combo_index)
    for it in (formulation or {}).get("ingredients", []):
        iid = it.get("ingredient_id")
        if not iid or iid == "WATER":
            continue
        j = ing_index.get(iid)
        if j is not None:
            x[offset + j] = float(it.get("dosage_kg", 0.0))

    x[offset + len(ing_index) + 0] = float(end_ph)
    x[offset + len(ing_index) + 1] = float(ferm_time_h)

    w_sy = np.array(model["weights_syneresis"], dtype=float)
    w_ov = np.array(model["weights_overall"], dtype=float)
    return float(x@w_sy), float(x@w_ov)

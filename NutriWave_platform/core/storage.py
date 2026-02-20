from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "data.json"
RUNS_PATH = ROOT / "data" / "runs.jsonl"
MODELS_PATH = ROOT / "data" / "models.jsonl"

def load_data() -> Dict[str, Any]:
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = dict(record)
    rec.setdefault("timestamp_utc", datetime.utcnow().isoformat())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def append_run(record: Dict[str, Any]) -> None:
    _append_jsonl(RUNS_PATH, record)

def append_model(record: Dict[str, Any]) -> None:
    _append_jsonl(MODELS_PATH, record)

def _read_jsonl(path: Path, limit: int = 500) -> List[Dict[str, Any]]:
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

def iter_runs(limit: int = 500) -> List[Dict[str, Any]]:
    return _read_jsonl(RUNS_PATH, limit=limit)

def iter_models(limit: int = 200) -> List[Dict[str, Any]]:
    return _read_jsonl(MODELS_PATH, limit=limit)

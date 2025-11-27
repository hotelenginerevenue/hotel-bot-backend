import json
from pathlib import Path

def load_reservations(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_reservations(data: dict, path: Path):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

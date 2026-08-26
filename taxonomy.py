from __future__ import annotations

import json
from pathlib import Path

_DATA_PATH = Path(__file__).with_name("taxonomy.json")

with _DATA_PATH.open(encoding="utf-8") as _source:
    TAXONOMIA_COMPLETA: dict[str, dict[str, list[str]]] = json.load(_source)

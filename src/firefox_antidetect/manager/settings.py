"""Global app settings (NOT per-profile) — currently the SX.org gateway
credentials. Stored as JSON next to profiles.db in the app-data dir.

Shape:
    {"sx": {"host": "<gateway>", "port": <int>, "password": "<shared pw>",
             "api_key": "<optional, for future directory/port-create calls>"}}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from . import paths


def settings_path(base: Optional[Path] = None) -> Path:
    return paths.app_data_dir(base) / "settings.json"


def load_settings(base: Optional[Path] = None) -> Dict[str, Any]:
    p = settings_path(base)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def save_settings(data: Dict[str, Any], base: Optional[Path] = None) -> None:
    settings_path(base).write_text(json.dumps(data, indent=2), encoding="utf-8")

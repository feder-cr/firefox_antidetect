"""Filesystem layout for the manager: app-data dir, profiles.db, per-profile dirs."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import platformdirs


def app_data_dir(base: Optional[Path] = None) -> Path:
    d = base if base is not None else Path(platformdirs.user_data_dir("invisible-manager"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path(base: Optional[Path] = None) -> Path:
    return app_data_dir(base) / "profiles.db"


def profiles_root(base: Optional[Path] = None) -> Path:
    d = app_data_dir(base) / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def profile_dir(profile_id: str, base: Optional[Path] = None) -> Path:
    d = profiles_root(base) / profile_id
    d.mkdir(parents=True, exist_ok=True)
    return d

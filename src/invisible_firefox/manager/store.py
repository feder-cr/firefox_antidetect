"""SQLite-backed profile metadata store."""
from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path
from typing import List, Optional

from .models import Profile

_COLS = ["id", "name", "seed", "pin", "proxy", "locale", "timezone",
         "binary_ver", "notes", "created_at", "last_used_at"]


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ProfileStore:
    def __init__(self, db_file: Path) -> None:
        self._db = Path(db_file)
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS profiles ("
                "id TEXT PRIMARY KEY, name TEXT, seed INTEGER, pin TEXT, proxy TEXT,"
                "locale TEXT, timezone TEXT, binary_ver TEXT, notes TEXT,"
                "created_at TEXT, last_used_at TEXT)"
            )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, profile: Profile) -> Profile:
        profile.created_at = profile.created_at or utc_now_iso()
        row = profile.to_row()
        with self._conn() as c:
            c.execute(
                f"INSERT INTO profiles ({','.join(_COLS)}) VALUES ({','.join('?' for _ in _COLS)})",
                [row[k] for k in _COLS],
            )
        return profile

    def get(self, id: str) -> Optional[Profile]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM profiles WHERE id=?", (id,)).fetchone()
        return Profile.from_row(dict(r)) if r else None

    def list(self) -> List[Profile]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM profiles ORDER BY created_at DESC").fetchall()
        return [Profile.from_row(dict(r)) for r in rows]

    def update(self, profile: Profile) -> None:
        row = profile.to_row()
        sets = ",".join(f"{k}=?" for k in _COLS if k != "id")
        with self._conn() as c:
            c.execute(f"UPDATE profiles SET {sets} WHERE id=?",
                      [row[k] for k in _COLS if k != "id"] + [profile.id])

    def delete(self, id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM profiles WHERE id=?", (id,))

    def touch(self, id: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE profiles SET last_used_at=? WHERE id=?", (utc_now_iso(), id))

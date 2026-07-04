"""The Profile record: one persistent browser identity."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Profile:
    id: str
    name: str
    seed: int
    pin: Optional[Dict[str, Any]] = None
    proxy: Optional[Dict[str, str]] = None
    locale: str = "auto"
    timezone: str = "auto"
    binary_ver: Optional[str] = None
    notes: str = ""
    created_at: str = ""
    last_used_at: str = ""

    @classmethod
    def new(cls, name: str, seed: int, **kw: Any) -> "Profile":
        return cls(id=uuid.uuid4().hex, name=name, seed=seed, **kw)

    def to_row(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "seed": self.seed,
            "pin": json.dumps(self.pin) if self.pin is not None else None,
            "proxy": json.dumps(self.proxy) if self.proxy is not None else None,
            "locale": self.locale, "timezone": self.timezone,
            "binary_ver": self.binary_ver, "notes": self.notes,
            "created_at": self.created_at, "last_used_at": self.last_used_at,
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Profile":
        d = dict(row)
        d["pin"] = json.loads(d["pin"]) if d.get("pin") else None
        d["proxy"] = json.loads(d["proxy"]) if d.get("proxy") else None
        return cls(**d)

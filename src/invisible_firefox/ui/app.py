"""App entry point. The UI is the pywebview web app (`web_app`); this thin
module keeps the stable ``run()`` that ``python -m invisible_firefox`` calls."""
from __future__ import annotations

from .web_app import Api, run

__all__ = ["run", "Api"]

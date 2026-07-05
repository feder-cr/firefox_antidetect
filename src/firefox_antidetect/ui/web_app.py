"""Web UI (pywebview) - the real app. Renders the shadcn interface in a native
window and bridges it to the pure-Python manager lib via a JS<->Python API.

`Api` is the whole surface JS can call (``window.pywebview.api.<method>``); it is
unit-testable on its own (see tests/test_web_api.py) without opening a window."""
from __future__ import annotations

import secrets
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..manager.store import ProfileStore
from ..manager.models import Profile
from ..manager import launcher as _launcher
from ..manager import paths
from ..manager import settings as _settings
from ..manager import sx as _sx
from ..manager.fingerprint import fingerprint_summary


def _seed_int(v: Any) -> int:
    """Accept an int, a decimal string, or a ``0x``/bare-hex string -> 32-bit int."""
    if isinstance(v, bool):
        raise ValueError("seed must be a number")
    if isinstance(v, int):
        return v & 0xFFFFFFFF
    s = str(v).strip()
    if not s:
        raise ValueError("seed is empty")
    if s.lower().startswith("0x"):
        return int(s, 16) & 0xFFFFFFFF
    try:
        return int(s) & 0xFFFFFFFF
    except ValueError:
        return int(s, 16) & 0xFFFFFFFF


def _seed_hex(seed: int) -> str:
    return f"0x{seed & 0xFFFFFFFF:08X}"


def _fp_view(seed: int, pin: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        return fingerprint_summary(seed, pin)
    except Exception as e:  # a bad seed/pin should not crash the UI
        return {"error": str(e)}


class Api:
    """Everything the web UI can invoke. Pure Python, no webview import - so it
    is testable headless. Each method returns JSON-serialisable data; mutating
    calls return ``{"ok": bool, ...}`` and never raise across the JS bridge."""

    def __init__(self, store: ProfileStore, base: Optional[Path] = None) -> None:
        self.store = store
        self.base = base
        self._handles: Dict[str, Any] = {}  # profile_id -> LaunchHandle
        # NOTE: never store the pywebview Window as a public attribute here - it
        # is the js_api object and pywebview would try to serialize the attribute
        # into JS, recursing forever over the native .NET window. Reach the window
        # via webview.windows in _notify() instead.

    # ----- helpers -----
    def _running(self, pid: str) -> bool:
        h = self._handles.get(pid)
        if h is None:
            return False
        proc = getattr(h, "process", None)
        poll = getattr(proc, "poll", None)
        return poll() is None if callable(poll) else True

    def _watch_exit(self, pid: str, handle: Any) -> None:
        """Block a daemon thread on the launched process; when the user closes
        the browser it exits and we push a UI refresh (event-driven, no polling
        lag). A light JS poll is the safety net for anything this misses."""
        proc = getattr(handle, "process", None)
        wait = getattr(proc, "wait", None)
        if not callable(wait):
            return

        def _run() -> None:
            try:
                proc.wait()
            except Exception:
                pass
            self._notify()

        threading.Thread(target=_run, daemon=True).start()

    def _notify(self) -> None:
        """Nudge the UI to re-sync its running statuses (called off-thread)."""
        try:
            import webview
            wins = getattr(webview, "windows", None)
            if wins:
                wins[0].run_js("window.__syncStatuses && window.__syncStatuses()")
        except Exception:
            pass

    def _row(self, p: Profile) -> Dict[str, Any]:
        return {
            "id": p.id,
            "name": p.name,
            "seed": p.seed,
            "seed_hex": _seed_hex(p.seed),
            "proxy": p.proxy,
            "locale": p.locale,
            "timezone": p.timezone,
            "binary_ver": p.binary_ver,
            "last_used_at": p.last_used_at,
            "running": self._running(p.id),
            "fp": _fp_view(p.seed, p.pin),
        }

    # ----- exposed to JS -----
    def list_profiles(self) -> List[Dict[str, Any]]:
        return [self._row(p) for p in self.store.list()]

    def get_profile(self, pid: str) -> Optional[Dict[str, Any]]:
        p = self.store.get(pid)
        return self._row(p) if p else None

    def fingerprint_preview(self, seed: Any) -> Dict[str, Any]:
        try:
            return _fp_view(_seed_int(seed))
        except Exception as e:
            return {"error": str(e)}

    def new_seed(self) -> Dict[str, Any]:
        s = secrets.randbits(32)
        return {"seed": s, "seed_hex": _seed_hex(s)}

    def save_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create (no id) or update (with id). ``data.proxy`` is either null
        (direct) or a dict; the UI only offers SX.ORG or no proxy."""
        try:
            seed = _seed_int(data.get("seed"))
            proxy = data.get("proxy") or None
            name = (data.get("name") or "").strip() or "Untitled"
            locale = (data.get("locale") or "auto").strip() or "auto"
            timezone = (data.get("timezone") or "auto").strip() or "auto"
            binary_ver = (data.get("binary_ver") or "").strip() or None
            pid = data.get("id")
            if pid:
                p = self.store.get(pid)
                if not p:
                    return {"ok": False, "error": "profile not found"}
                p.name, p.seed, p.proxy = name, seed, proxy
                p.locale, p.timezone, p.binary_ver = locale, timezone, binary_ver
                self.store.update(p)
            else:
                p = Profile.new(name=name, seed=seed, proxy=proxy,
                                locale=locale, timezone=timezone, binary_ver=binary_ver)
                self.store.create(p)
            return {"ok": True, "profile": self._row(p)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_profile(self, pid: str) -> Dict[str, Any]:
        try:
            self.store.delete(pid)
            self._handles.pop(pid, None)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def launch_profile(self, pid: str) -> Dict[str, Any]:
        p = self.store.get(pid)
        if not p:
            return {"ok": False, "error": "profile not found"}
        try:
            handle = _launcher.launch(p, base=self.base)
            self._handles[pid] = handle
            self.store.touch(pid)
            self._watch_exit(pid, handle)  # push a refresh when the browser closes
            return {"ok": True, "pid": handle.pid}
        except Exception as e:
            # dead proxy / missing binary / geo / SX-not-configured surface here
            return {"ok": False, "error": str(e)}

    def stop_profile(self, pid: str) -> Dict[str, Any]:
        """Close a running profile's browser from the manager."""
        h = self._handles.get(pid)
        proc = getattr(h, "process", None)
        poll = getattr(proc, "poll", None)
        if proc is not None and callable(poll) and poll() is None:
            try:
                proc.terminate()
            except Exception as e:
                return {"ok": False, "error": str(e)}
        return {"ok": True}

    def statuses(self) -> Dict[str, bool]:
        """Lightweight per-profile running map for the UI's live refresh (no
        fingerprint recompute - cheap to poll)."""
        return {p.id: self._running(p.id) for p in self.store.list()}

    # ----- Proxies menu (global SX settings) -----
    def get_settings(self) -> Dict[str, Any]:
        return _settings.load_settings(self.base)

    def save_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            _settings.save_settings(data or {}, self.base)
            return {"ok": True, "configured": self.sx_configured()["configured"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sx_configured(self) -> Dict[str, Any]:
        """Whether an SX API key is set - drives the editor's 'set up key' banner
        without exposing the key itself."""
        return {"configured": bool(_sx.api_key_of(_settings.load_settings(self.base)))}

    def sx_check_key(self, api_key: str) -> Dict[str, Any]:
        """Validate a key against the SX API (used by the Proxies menu 'Test')."""
        return _sx.check_api_key(api_key)

    def sx_countries(self) -> Dict[str, Any]:
        """SX directory country list for the editor's Country dropdown."""
        key = _sx.api_key_of(_settings.load_settings(self.base))
        if not key:
            return {"ok": False, "error": "no api key"}
        try:
            return {"ok": True, "countries": _sx.list_countries(key)}
        except _sx.SxError as e:
            return {"ok": False, "error": str(e)}

    def sx_cities(self, country_id: Any) -> Dict[str, Any]:
        """SX directory cities for a numeric country id (cascaded from Country)."""
        key = _sx.api_key_of(_settings.load_settings(self.base))
        if not key:
            return {"ok": False, "error": "no api key"}
        try:
            return {"ok": True, "cities": _sx.list_cities(key, country_id)}
        except _sx.SxError as e:
            return {"ok": False, "error": str(e)}


def _index_html() -> str:
    return (Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8")


def run() -> int:
    import webview  # imported lazily so the lib/tests don't need a GUI runtime

    store = ProfileStore(paths.db_path())
    api = Api(store, base=None)
    webview.create_window(
        "firefox_antidetect",
        html=_index_html(),
        js_api=api,
        width=1180,
        height=760,
        min_size=(920, 600),
        background_color="#0E1216",
    )
    webview.start()
    return 0

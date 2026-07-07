"""Direct-launch orchestration: Profile -> running patched Firefox subprocess."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import psutil  # cross-platform process tree (Win/Linux/mac)
except Exception:  # pragma: no cover - psutil is a declared dependency
    psutil = None  # type: ignore

from invisible_core import build_launch_plan as _core_build_launch_plan, LaunchPlan

from .models import Profile
from . import paths
from . import settings as _settings
from . import sx as _sx


def resolve_launch_proxy(proxy: Optional[Dict[str, Any]], base: Optional[Path] = None):
    """A profile's ``proxy`` is an INTENT. Turn it into a concrete proxy dict:
    ``None`` -> ``None``; an SX intent (``{"provider":"sx",...}``) -> a live
    SOCKS5 endpoint via the SX API; an already-concrete ``{"server":...}`` dict
    -> itself."""
    if not proxy:
        return None
    if proxy.get("provider") == "sx":
        return _sx.resolve_proxy(proxy, _settings.load_settings(base))
    return proxy


@dataclass
class LaunchHandle:
    pid: int              # the REAL browser pid (resolved), NOT the launcher stub on Windows
    profile_id: str
    process: Any          # the subprocess.Popen we spawned (the launcher stub on Windows)
    browser: Any = None   # psutil.Process of the real browser, when resolved (else None)


def build_launch_plan(profile: Profile, base: Optional[Path] = None) -> LaunchPlan:
    """Resolve the profile's proxy intent (SX -> concrete endpoint) and its
    profile dir, then delegate the whole session setup to
    ``invisible_core.build_launch_plan``. The manager owns only SX resolution and
    where the profile lives; the fingerprint, geo, prefs, user.js, env and argv
    are all invisible_core's job (one shared code path with the wrapper)."""
    rproxy = resolve_launch_proxy(profile.proxy, base)  # SX intent -> concrete endpoint
    pdir = paths.profile_dir(profile.id, base=base)
    return _core_build_launch_plan(
        profile.seed,
        profile_dir=pdir,
        proxy=rproxy,
        timezone=profile.timezone,
        locale=profile.locale,
        pin=profile.pin,
        binary_ver=profile.binary_ver,
    )


# ─────────────────────────────────────────────────────────────────────────
#  Cross-OS process tracking (Win/Linux/mac)
# ─────────────────────────────────────────────────────────────────────────
# The pid we get from Popen is NOT always the browser:
#   Windows - `firefox.exe` is a "launcher process" that spawns the real
#             browser as its FIRST CHILD and then EXITS (Mozilla design, see
#             wiki.mozilla.org/.../Launcher_Process). So Popen's pid dies in
#             ~1s and the browser lives under a different pid.
#   Linux   - the `firefox` script `exec`s firefox-bin in place: Popen's pid
#             IS the browser.
#   macOS   - the launched binary IS the browser (no launcher process).
# We resolve the real browser uniformly by the PROFILE DIR in its cmdline
# (unique per profile, present on every OS) and track THAT via psutil, so
# running-status and stop work identically everywhere.


def _is_main_firefox(p: "psutil.Process", target: str) -> bool:
    """True iff psutil process ``p`` is a MAIN firefox browser (not a content
    child) launched with ``-profile <target>``."""
    try:
        cmd = p.cmdline()
        name = (p.name() or "").lower()
    except Exception:
        return False
    if not cmd or "-contentproc" in cmd:
        return False
    exe0 = (cmd[0] or "").lower()
    if not (name.startswith("firefox") or "firefox" in exe0):
        return False
    return any(target in (c or "") for c in cmd)


def _has_contentproc_child(p: "psutil.Process") -> bool:
    """True if ``p`` has at least one ``-contentproc`` firefox child. The REAL
    browser spawns content processes; the Windows launcher stub does not - so
    this cleanly tells the browser from the stub even while both exist."""
    try:
        for c in p.children(recursive=False):
            try:
                if "-contentproc" in c.cmdline():
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def resolve_browser_process(profile_dir: Path, popen_proc: Any, timeout: float = 8.0) -> Any:
    """Return the psutil.Process of the REAL browser for this profile, or None.

    The browser is the main firefox process (``-profile <dir>``, not a
    ``-contentproc`` child) that HAS content-process children. That test is what
    makes this reliable cross-OS: on Windows the launcher stub also matches the
    ``-profile`` filter but never spawns content children, so it is never
    mistaken for the browser; on Linux/macOS the launched process is the browser
    and has them. Falls back to any alive main-firefox match if content children
    have not appeared before the timeout."""
    if psutil is None:
        return None
    target = str(profile_dir)
    launched_pid = getattr(popen_proc, "pid", None)
    start = time.monotonic()
    fallback = None
    while time.monotonic() - start < timeout:
        candidates: List[Any] = []
        seen = set()
        # Prefer the stub's subtree (Windows), then a global scan (Linux/mac +
        # re-parented Windows child once the stub has exited).
        if launched_pid is not None:
            try:
                for c in psutil.Process(launched_pid).children(recursive=True):
                    if _is_main_firefox(c, target):
                        candidates.append(c)
                        seen.add(c.pid)
            except Exception:
                pass
        try:
            for p in psutil.process_iter(["name"]):
                if not (p.info.get("name") or "").lower().startswith("firefox"):
                    continue
                if p.pid in seen:
                    continue
                if _is_main_firefox(p, target):
                    candidates.append(p)
        except Exception:
            pass
        for c in candidates:
            if _has_contentproc_child(c):
                return c  # unambiguously the real browser
        alive = [c for c in candidates if c.is_running()]
        if alive:
            fallback = alive[0]
        time.sleep(0.25)
    return fallback


def process_alive(psproc: Any) -> bool:
    """Cross-OS liveness for a psutil.Process (False if gone or a zombie)."""
    if psproc is None or psutil is None:
        return False
    try:
        return psproc.is_running() and psproc.status() != psutil.STATUS_ZOMBIE
    except Exception:
        return False


def terminate_process_tree(psproc: Any, timeout: float = 5.0) -> None:
    """Terminate a browser and all its child processes, cross-OS. Graceful
    terminate() first, then kill() any survivors."""
    if psproc is None or psutil is None:
        return
    try:
        procs = psproc.children(recursive=True)
    except Exception:
        procs = []
    procs.append(psproc)
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    try:
        _gone, alive = psutil.wait_procs(procs, timeout=timeout)
    except Exception:
        alive = procs
    for p in alive:
        try:
            p.kill()
        except Exception:
            pass


def launch(
    profile: Profile,
    base: Optional[Path] = None,
    spawn: Callable[..., Any] = subprocess.Popen,
) -> LaunchHandle:
    plan = build_launch_plan(profile, base=base)
    proc = spawn(plan.argv, env=plan.env)
    # Only resolve the real browser on a REAL launch; an injected spawn (tests)
    # keeps the raw process so its pid/handle stay predictable.
    browser = None
    real_pid = proc.pid
    if spawn is subprocess.Popen:
        browser = resolve_browser_process(plan.profile_dir, proc)
        if browser is not None:
            real_pid = browser.pid
    return LaunchHandle(pid=real_pid, profile_id=profile.id, process=proc, browser=browser)

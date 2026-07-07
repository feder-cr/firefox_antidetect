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

from invisible_core import (
    ensure_binary,
    prepare_session_geo,
    resolve_session_locale,
    generate_profile,
    translate_profile_to_prefs,
    configure_proxy,
    write_user_js,
    build_launch_env,
)
from invisible_core._geo import SessionGeo as _SessionGeo  # for test stubs + typing

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
class LaunchPlan:
    binary: str
    profile_dir: Path
    argv: List[str]
    env: Dict[str, str]


@dataclass
class LaunchHandle:
    pid: int              # the REAL browser pid (resolved), NOT the launcher stub on Windows
    profile_id: str
    process: Any          # the subprocess.Popen we spawned (the launcher stub on Windows)
    browser: Any = None   # psutil.Process of the real browser, when resolved (else None)


def _loc(locale: str, geo: "_SessionGeo", proxy: Optional[Dict[str, str]]) -> str:
    """Resolve a ``"auto"`` locale to a concrete BCP-47 tag from the egress
    (reusing the egress IP already discovered for the timezone); pass an
    explicit tag through. ``translate_profile_to_prefs`` needs a real tag -
    it does NOT special-case ``"auto"``."""
    if (locale or "").strip().lower() == "auto":
        return resolve_session_locale(geo.egress_ip, proxy)
    return locale


def build_launch_plan(profile: Profile, base: Optional[Path] = None) -> LaunchPlan:
    binary = str(ensure_binary(profile.binary_ver) if profile.binary_ver else ensure_binary())
    rproxy = resolve_launch_proxy(profile.proxy, base)  # SX intent -> live SOCKS5 endpoint
    geo = prepare_session_geo(profile.timezone, rproxy)  # raises behind a dead proxy (by design)
    fp = generate_profile(seed=profile.seed, pin=profile.pin)
    prefs = translate_profile_to_prefs(
        fp, locale=_loc(profile.locale, geo, rproxy), timezone=geo.timezone
    )
    configure_proxy(rproxy, prefs)  # mutates prefs for SOCKS auth
    pdir = paths.profile_dir(profile.id, base=base)
    write_user_js(pdir, prefs)
    env = build_launch_env(prefs, timezone=geo.timezone or None, egress_ip=geo.egress_ip)
    argv = [binary, "-no-remote", "-profile", str(pdir), "about:blank"]
    return LaunchPlan(binary=binary, profile_dir=pdir, argv=argv, env=env)


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


def resolve_browser_process(
    profile_dir: Path, popen_proc: Any, timeout: float = 6.0, settle: float = 1.5
) -> Any:
    """Return the psutil.Process of the REAL browser for this profile, or None.

    Handles all three OSes: on Windows it grabs the child the launcher stub
    spawned (or finds it after the stub exits); on Linux/macOS it confirms the
    launched process itself is the browser."""
    if psutil is None:
        return None
    target = str(profile_dir)
    launched_pid = getattr(popen_proc, "pid", None)
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        # (1) Windows: a firefox child of the launcher stub with our profile.
        if launched_pid is not None:
            try:
                for c in psutil.Process(launched_pid).children(recursive=True):
                    if _is_main_firefox(c, target):
                        return c
            except Exception:
                pass  # stub already exited -> fall through to the scan
        # (2) Scan for a main firefox with our profile that isn't the stub.
        launched_match = None
        try:
            for p in psutil.process_iter(["name"]):
                nm = (p.info.get("name") or "").lower()
                if not nm.startswith("firefox"):
                    continue
                if not _is_main_firefox(p, target):
                    continue
                if p.pid == launched_pid:
                    launched_match = p
                else:
                    return p  # the real (re-parented) browser
        except Exception:
            pass
        # (3) Linux/macOS: the launched process itself is the browser and stays
        # alive past the settle window (the Windows stub would have exited).
        try:
            stub_alive = popen_proc.poll() is None
        except Exception:
            stub_alive = launched_match is not None
        if launched_match is not None and stub_alive and (time.monotonic() - start) >= settle:
            return launched_match
        time.sleep(0.25)
    return None


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

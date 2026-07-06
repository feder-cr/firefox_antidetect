"""Direct-launch orchestration: Profile -> running patched Firefox subprocess."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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
    pid: int
    profile_id: str
    process: Any


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


def launch(
    profile: Profile,
    base: Optional[Path] = None,
    spawn: Callable[..., Any] = subprocess.Popen,
) -> LaunchHandle:
    plan = build_launch_plan(profile, base=base)
    proc = spawn(plan.argv, env=plan.env)
    return LaunchHandle(pid=proc.pid, profile_id=profile.id, process=proc)

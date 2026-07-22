import os
import time

import pytest

from invisible_firefox.manager.models import Profile
from invisible_firefox.manager import launcher as L
from invisible_core.launch import LaunchPlan


def _fake_plan(tmp_path):
    pdir = tmp_path / "profiles" / "x"
    pdir.mkdir(parents=True, exist_ok=True)
    return LaunchPlan(
        binary="/fake/firefox",
        profile_dir=pdir,
        argv=["/fake/firefox", "-no-remote", "-profile", str(pdir), "about:blank"],
        env={"STEALTHFOX_WEBRTC_PUBLIC_IP": "1.2.3.4"},
    )


def test_build_launch_plan_delegates_to_core(tmp_path, monkeypatch):
    """The manager only resolves the SX proxy + profile dir; everything else is
    handed to invisible_core.build_launch_plan with the profile's settings."""
    captured = {}

    def fake_core(seed, **kw):
        captured["seed"] = seed
        captured.update(kw)
        return _fake_plan(tmp_path)

    monkeypatch.setattr(L, "_core_build_launch_plan", fake_core)

    p = Profile.new(
        name="A", seed=42, proxy={"server": "socks5://h:1"},
        timezone="America/New_York", locale="en-US",
    )
    plan = L.build_launch_plan(p, base=tmp_path)

    assert captured["seed"] == 42
    assert captured["proxy"] == {"server": "socks5://h:1"}  # concrete proxy passes through
    assert captured["timezone"] == "America/New_York"
    assert captured["locale"] == "en-US"
    assert captured["pin"] == p.pin
    assert captured["binary_ver"] == p.binary_ver
    assert captured["profile_dir"] == tmp_path / "profiles" / p.id
    assert plan.argv[0] == "/fake/firefox"


def test_sx_proxy_intent_is_resolved_before_core(tmp_path, monkeypatch):
    """An SX proxy INTENT is turned into a concrete endpoint by the manager
    before invisible_core ever sees it."""
    monkeypatch.setattr(L._sx, "resolve_proxy",
                        lambda proxy, settings: {"server": "socks5://sx:9"})
    captured = {}

    def fake_core(seed, **kw):
        captured.update(kw)
        return _fake_plan(tmp_path)

    monkeypatch.setattr(L, "_core_build_launch_plan", fake_core)
    p = Profile.new(name="A", seed=1, proxy={"provider": "sx", "country": "us"})
    L.build_launch_plan(p, base=tmp_path)
    assert captured["proxy"] == {"server": "socks5://sx:9"}


def test_launch_uses_injected_spawn(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "_core_build_launch_plan", lambda seed, **kw: _fake_plan(tmp_path))

    calls = {}

    class FakeProc:
        pid = 4321

    def fake_spawn(argv, env=None, **kw):
        calls["argv"], calls["env"] = argv, env
        return FakeProc()

    p = Profile.new(name="A", seed=1)
    h = L.launch(p, base=tmp_path, spawn=fake_spawn)
    assert h.pid == 4321 and h.profile_id == p.id  # injected spawn -> no psutil resolve
    assert h.browser is None
    assert calls["argv"][0] == "/fake/firefox"


@pytest.mark.integration
def test_real_launch_starts_and_exits(tmp_path):
    """Launches the real binary headless and confirms the process starts.
    Opt-in: run with `python -m pytest -m integration`. Needs the cached binary
    (or network for ensure_binary)."""
    os.environ["MOZ_HEADLESS"] = "1"
    p = Profile.new(name="it", seed=999)
    h = L.launch(p, base=tmp_path)
    time.sleep(3)
    # started (running or clean-exited); on Windows h.process is the launcher stub
    assert h.process.poll() is None or h.process.poll() == 0
    if h.browser is not None:
        L.terminate_process_tree(h.browser)
    else:
        h.process.terminate()

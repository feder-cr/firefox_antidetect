import os
import time
from pathlib import Path

import pytest

from firefox_antidetect.manager.models import Profile
from firefox_antidetect.manager import launcher as L


def _stub_core(monkeypatch, tz="America/New_York", egress="1.2.3.4"):
    monkeypatch.setattr(L, "ensure_binary", lambda ver=None: "/fake/firefox")
    monkeypatch.setattr(L, "prepare_session_geo", lambda tzarg, proxy: L._SessionGeo(tz, egress))
    monkeypatch.setattr(L, "resolve_session_locale", lambda ip, proxy: "en-US")
    monkeypatch.setattr(L, "generate_profile", lambda seed, pin=None: object())
    monkeypatch.setattr(L, "translate_profile_to_prefs",
                        lambda fp, **kw: {"intl.accept_languages": "en-US, en"})
    monkeypatch.setattr(L, "configure_proxy", lambda proxy, prefs: None)


def test_build_launch_plan_writes_user_js_and_argv(tmp_path, monkeypatch):
    _stub_core(monkeypatch)
    p = Profile.new(name="A", seed=42, proxy={"server": "socks5://h:1"})
    plan = L.build_launch_plan(p, base=tmp_path)

    assert plan.binary == "/fake/firefox"
    assert plan.profile_dir == tmp_path / "profiles" / p.id
    assert (plan.profile_dir / "user.js").exists()
    assert plan.argv[0] == "/fake/firefox"
    assert "-profile" in plan.argv and str(plan.profile_dir) in plan.argv
    assert "-no-remote" in plan.argv
    assert plan.env["STEALTHFOX_WEBRTC_PUBLIC_IP"] == "1.2.3.4"


def test_launch_uses_injected_spawn(tmp_path, monkeypatch):
    _stub_core(monkeypatch, tz="", egress=None)

    calls = {}

    class FakeProc:
        pid = 4321

    def fake_spawn(argv, env=None, **kw):
        calls["argv"], calls["env"] = argv, env
        return FakeProc()

    p = Profile.new(name="A", seed=1)
    h = L.launch(p, base=tmp_path, spawn=fake_spawn)
    assert h.pid == 4321 and h.profile_id == p.id
    assert calls["argv"][0] == "/fake/firefox"


@pytest.mark.integration
def test_real_launch_starts_and_exits(tmp_path):
    """Launches the real firefox-14 headless and confirms the process starts.
    Opt-in: run with `python -m pytest -m integration`. Needs the cached binary
    (or network for ensure_binary)."""
    os.environ["MOZ_HEADLESS"] = "1"
    p = Profile.new(name="it", seed=999)
    h = L.launch(p, base=tmp_path)
    time.sleep(3)
    assert h.process.poll() is None or h.process.poll() == 0  # started (running or clean-exited)
    h.process.terminate()

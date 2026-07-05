"""Live-status API: statuses() reports the running map, stop_profile() is graceful."""
import firefox_antidetect.ui.web_app as web_app
from firefox_antidetect.manager.store import ProfileStore
from firefox_antidetect.ui.web_app import Api


def _api(tmp_path):
    return Api(ProfileStore(tmp_path / "p.db"), base=tmp_path)


def test_binary_version_and_prefetch(tmp_path, monkeypatch):
    # mock ensure_binary so the prefetch thread never hits the network in tests
    monkeypatch.setattr(web_app, "_ensure_binary", lambda *a, **k: tmp_path / "firefox")
    api = _api(tmp_path)
    assert api.binary_version()  # non-empty version string
    assert api.prefetch_binary()["ok"] is True


def test_statuses_idle_for_never_launched(tmp_path):
    api = _api(tmp_path)
    pid = api.save_profile({"name": "A", "seed": "1"})["profile"]["id"]
    assert api.statuses() == {pid: False}


def test_stop_missing_is_graceful(tmp_path):
    assert _api(tmp_path).stop_profile("nope")["ok"] is True


def test_running_reflects_handle_and_stop(tmp_path):
    api = _api(tmp_path)
    pid = api.save_profile({"name": "A", "seed": "1"})["profile"]["id"]

    class _Proc:
        def __init__(self): self._alive = True
        def poll(self): return None if self._alive else 0
        def terminate(self): self._alive = False

    class _H:
        pid = 1234
        process = _Proc()

    api._handles[pid] = _H()
    assert api.statuses() == {pid: True}
    assert api.stop_profile(pid)["ok"] is True
    assert api.statuses() == {pid: False}

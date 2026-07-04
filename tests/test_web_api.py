"""The web UI's whole surface is the `Api` bridge — test it headless (no window)."""
from __future__ import annotations

import pytest

from firefox_antidetect.manager.store import ProfileStore
from firefox_antidetect.ui.web_app import Api, _seed_int


def _api(tmp_path):
    return Api(ProfileStore(tmp_path / "p.db"), base=tmp_path)


def test_seed_int_accepts_hex_dec_and_bare_hex():
    assert _seed_int("0x5EAFBABE") == 0x5EAFBABE
    assert _seed_int("12345") == 12345
    assert _seed_int("deadbeef") == 0xDEADBEEF
    assert _seed_int(0x1_0000_0001) == 1  # masked to 32-bit


def test_create_list_and_row_shape(tmp_path):
    api = _api(tmp_path)
    assert api.list_profiles() == []
    res = api.save_profile({"name": "Retail US", "seed": "0x5EAFBABE", "proxy": None,
                            "locale": "en-US", "timezone": "America/New_York"})
    assert res["ok"] is True
    rows = api.list_profiles()
    assert len(rows) == 1
    r = rows[0]
    assert r["name"] == "Retail US"
    assert r["seed_hex"] == "0x5EAFBABE"
    assert r["proxy"] is None
    assert r["running"] is False
    # fingerprint preview embedded in the row
    assert r["fp"]["screen"] and r["fp"]["hardware_concurrency"]


def test_update_and_delete(tmp_path):
    api = _api(tmp_path)
    pid = api.save_profile({"name": "A", "seed": "1"})["profile"]["id"]
    upd = api.save_profile({"id": pid, "name": "A2", "seed": "2",
                            "proxy": {"provider": "sx", "country": "DE", "rotation": "sticky"}})
    assert upd["ok"] and upd["profile"]["name"] == "A2"
    assert upd["profile"]["proxy"]["country"] == "DE"
    assert api.delete_profile(pid)["ok"] is True
    assert api.list_profiles() == []


def test_fingerprint_preview_deterministic(tmp_path):
    api = _api(tmp_path)
    a = api.fingerprint_preview("0x5EAFBABE")
    b = api.fingerprint_preview("0x5EAFBABE")
    assert a == b and "screen" in a


def test_new_seed_is_32bit(tmp_path):
    s = _api(tmp_path).new_seed()
    assert 0 <= s["seed"] <= 0xFFFFFFFF
    assert s["seed_hex"].startswith("0x")


def test_save_bad_seed_returns_error_not_raise(tmp_path):
    res = _api(tmp_path).save_profile({"name": "x", "seed": "not-a-seed!!"})
    assert res["ok"] is False and res["error"]


def test_launch_missing_profile_is_graceful(tmp_path):
    res = _api(tmp_path).launch_profile("nope")
    assert res["ok"] is False

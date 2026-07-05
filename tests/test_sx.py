"""SX.org integration: username grammar, settings, and proxy resolution guards.
Network paths (check_api_key with a real key, resolve_proxy with a key) are NOT
exercised here — only the offline logic and the not-configured guards."""
from __future__ import annotations

import pytest

from firefox_antidetect.manager import sx, settings
from firefox_antidetect.manager.launcher import resolve_launch_proxy
from firefox_antidetect.manager.store import ProfileStore
from firefox_antidetect.ui.web_app import Api


def test_build_username_sticky_rotating_and_country_case():
    assert sx.build_username({"product": "residential", "country": "us", "session": "sticky"}) \
        == "res-country-US-hold-session"
    assert sx.build_username({"product": "residential", "country": "US", "session": "rotating"}) \
        == "res-country-US"
    # default product=residential, default session=sticky
    assert sx.build_username({"country": "de"}) == "res-country-DE-hold-session"
    assert sx.build_username({"product": "mobile", "country": "fr", "session": "sticky"}) \
        == "mobile-country-FR-hold-session"


def test_api_key_of():
    assert sx.api_key_of({"sx": {"api_key": "  K  "}}) == "K"
    assert sx.api_key_of({}) == ""
    assert sx.api_key_of({"sx": {}}) == ""


def test_resolve_proxy_without_key_raises():
    with pytest.raises(sx.SxError):
        sx.resolve_proxy({"provider": "sx", "country": "US"}, {})


def test_check_api_key_empty_is_not_ok_offline():
    r = sx.check_api_key("")
    assert r["ok"] is False


def test_settings_roundtrip(tmp_path):
    assert settings.load_settings(base=tmp_path) == {}
    settings.save_settings({"sx": {"api_key": "abc"}}, base=tmp_path)
    assert settings.load_settings(base=tmp_path)["sx"]["api_key"] == "abc"


def test_api_settings_and_sx_configured(tmp_path):
    api = Api(ProfileStore(tmp_path / "p.db"), base=tmp_path)
    assert api.sx_configured()["configured"] is False
    assert api.save_settings({"sx": {"api_key": "xyz"}})["ok"] is True
    assert api.sx_configured()["configured"] is True
    assert api.get_settings()["sx"]["api_key"] == "xyz"


def test_resolve_launch_proxy_passthrough_and_guard(tmp_path):
    assert resolve_launch_proxy(None, tmp_path) is None
    concrete = {"server": "socks5://h:1", "username": "u", "password": "p"}
    assert resolve_launch_proxy(concrete, tmp_path) == concrete
    # an SX intent with no api_key configured surfaces a clear error
    with pytest.raises(sx.SxError):
        resolve_launch_proxy({"provider": "sx", "country": "US"}, tmp_path)


def test_save_sx_profile_stores_intent(tmp_path):
    api = Api(ProfileStore(tmp_path / "p.db"), base=tmp_path)
    res = api.save_profile({"name": "SX", "seed": "0x1",
                            "proxy": {"provider": "sx", "product": "mobile",
                                      "country": "DE", "session": "sticky"}})
    assert res["ok"] is True
    row = api.list_profiles()[0]
    assert row["proxy"]["product"] == "mobile" and row["proxy"]["country"] == "DE"

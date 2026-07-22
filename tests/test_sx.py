"""SX.org integration: proxy-URL parsing, settings, and resolution guards.
The live network paths (check_api_key / directory / search with a real key) are
NOT exercised here - only the offline parse logic and the not-configured guards."""
from __future__ import annotations

import pytest

from invisible_firefox.manager import sx, settings
from invisible_firefox.manager.launcher import resolve_launch_proxy
from invisible_firefox.manager.store import ProfileStore
from invisible_firefox.ui.web_app import Api


def test_first_proxy_url_parses_search_array():
    # /v2/proxy/search returns [{"success": true}, "http://user:pass@host:port"]
    res = [{"success": True}, "http://u123-abc:pw456@212.8.248.20:9999"]
    assert sx._first_proxy_url(res) == "http://u123-abc:pw456@212.8.248.20:9999"
    # empty pool -> just the success element, no URL string
    assert sx._first_proxy_url([{"success": True}]) is None
    # tolerant of a dict form in case the schema shifts
    assert sx._first_proxy_url([{"host": "h", "port": 1, "username": "u", "password": "p"}]) \
        == "socks5://u:p@h:1"


def test_build_username_grammar():
    u = sx.build_username("acct", {"country": "us", "product": "residential", "session": "sticky"})
    assert u.startswith("acct-res-country-US-hold-session-session-")
    # rotating -> no session suffix
    assert sx.build_username("acct", {"country": "DE", "session": "rotating"}) == "acct-res-country-DE"
    # city id + mobile product
    u2 = sx.build_username("acct", {"country": "US", "city_id": 5102713, "product": "mobile"})
    assert u2.startswith("acct-mobile-country-US-city-5102713-hold-session-session-")
    # two calls -> different session ids (fresh sticky session each time)
    a = sx.build_username("acct", {"country": "US"})
    b = sx.build_username("acct", {"country": "US"})
    assert a != b


def test_resolve_proxy_uses_gateway_port_443_and_targeting_username(monkeypatch):
    # search gives an account credential (<base>-<uuid>:pass) + a host; resolve_proxy
    # reuses the host over socks5 on port 443 with a targeting username.
    monkeypatch.setattr(sx, "_get",
                        lambda path, key, params, **kw: [{"success": True},
                                                         "http://nd0base-abcd-1234:secretpw@1.2.3.4:9999"])
    got = sx.resolve_proxy({"provider": "sx", "country": "US"}, {"sx": {"api_key": "K"}})
    assert got["server"] == "socks5://1.2.3.4:443"          # NOT the 9999 in the URL
    assert got["password"] == "secretpw"
    assert got["username"].startswith("nd0base-res-country-US-hold-session-session-")  # base kept, targeting built


def test_resolve_proxy_empty_pool_raises(monkeypatch):
    # SX returns just [{"success": true}] when the requested pool is empty
    monkeypatch.setattr(sx, "_get", lambda path, key, params, **kw: [{"success": True}])
    with pytest.raises(sx.SxError):
        sx.resolve_proxy({"provider": "sx", "country": "KP"}, {"sx": {"api_key": "K"}})


def test_sx_directory_guards_without_key(tmp_path):
    api = Api(ProfileStore(tmp_path / "p.db"), base=tmp_path)
    assert api.sx_countries()["ok"] is False
    assert api.sx_cities(1)["ok"] is False


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

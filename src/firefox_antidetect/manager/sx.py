"""SX.org proxy integration. The user's ONLY credential is an **API key**
(set once in the Proxies menu); everything else is derived from it.

Per-profile intent (stored on ``Profile.proxy``):
    {"provider":"sx", "product":"residential"|"mobile"|"corporate",
     "country":"US", "session":"sticky"|"rotating", "traffic_gb": <num|null>}

Global credential (``settings["sx"]``):
    {"api_key": "<key from my.sx.org>"}

``resolve_proxy()`` turns the intent + api_key into a concrete SOCKS5 proxy
dict for ``invisible_core.configure_proxy``:
    {"server":"socks5://host:443", "username":..., "password":...}

Verified end-to-end against a live sx.org key (2026-07-07, HTTPS clean through
firefox-15). The model - reachable with the API KEY alone:
  * Auth is the ``apiKey`` QUERY param (a header gives 401).
  * ``/v2/proxy/search?country=CC`` returns ``[{"success": true},
    "http://<base>-<sess>:<password>@<host>:9999"]``. We take the HOST, the base
    username (the part before the first ``-``) and the password from it.
  * The proxy is then used over SOCKS5 on **port 443** - NOT the ``9999`` in the
    URL. Port 9999 SSL-BUMPS https (self-signed cert -> firefox
    SEC_ERROR_UNKNOWN_ISSUER); the SAME host on 443 tunnels cleanly. The
    username is a TARGETING username (``build_username``): the SX gateway grammar
    ``<base>-<product>-country-CC[-city-ID]-hold-session-session-<random>``.
  * ``/v2/dir/countries`` -> ``{"countries":[{id,code,name}]}`` and
    ``/v2/dir/cities?countryId=<id>`` -> ``{"cities":[{id,name,...}]}`` back the
    Country/City pickers.
"""
from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

API_BASE = "https://api.sx.org"
PRODUCTS = ("residential", "mobile", "corporate")

# SX serves clean-tunneling SOCKS5 on port 443 (the 9999 the search URL carries
# SSL-bumps https). Product tokens for the targeting-username grammar.
SOCKS_PORT = 443
_PREFIX = {"residential": "res", "mobile": "mobile", "corporate": "corp"}


class SxError(Exception):
    """SX integration failure (missing key, API error, no proxy available)."""


def api_key_of(settings: Dict[str, Any]) -> str:
    return str(((settings or {}).get("sx") or {}).get("api_key") or "").strip()


def build_username(base: str, sx: Dict[str, Any]) -> str:
    """Build the SX gateway TARGETING username for the given account base.

    Grammar (dash-delimited): ``<base>-<product>-country-<CC>[-city-<id>]`` and,
    for a sticky session, ``-hold-session-session-<random>`` (a fresh session id
    per call). ``<product>`` defaults to ``res`` (residential)."""
    product = _PREFIX.get((sx.get("product") or "residential").strip().lower(), "res")
    parts = [base, product, "country", (sx.get("country") or "US").upper()]
    city_id = sx.get("city_id") or sx.get("city")
    if city_id:
        parts += ["city", str(city_id)]                     # SX numeric city id
    if (sx.get("session") or "sticky").strip().lower() != "rotating":
        parts += ["hold-session", "session", secrets.token_hex(8)]
    return "-".join(parts)


def list_countries(api_key: str) -> list:
    """SX directory: [{"id": int, "name": str, "code": <ISO-2>}, ...]."""
    res = _get("/v2/dir/countries", api_key, {})
    return res.get("countries", []) if isinstance(res, dict) else []


def list_cities(api_key: str, country_id: Any) -> list:
    """SX directory cities for a numeric country id: [{"id": int, "name": str}, ...]."""
    res = _get("/v2/dir/cities", api_key, {"countryId": country_id})
    return res.get("cities", []) if isinstance(res, dict) else []


def _get(path: str, api_key: str, params: Dict[str, Any], timeout: float = 15.0) -> Any:
    q = dict(params or {})
    q["apiKey"] = api_key
    url = f"{API_BASE}{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise SxError(f"SX API {e.code} on {path}: {e.read().decode('utf-8','replace')[:160]}")
    except Exception as e:
        raise SxError(f"SX API unreachable ({path}): {e}")
    try:
        return json.loads(body)
    except ValueError:
        return body


def check_api_key(api_key: str) -> Dict[str, Any]:
    """Validate a key. Returns {"ok": bool, "detail": str}. Never raises."""
    api_key = (api_key or "").strip()
    if not api_key:
        return {"ok": False, "detail": "empty key"}
    try:
        info = _get("/v2/plan/info", api_key, {"showProxies": "all"})
        return {"ok": True, "detail": "valid", "plan": info}
    except SxError as e:
        return {"ok": False, "detail": str(e)}


def resolve_proxy(sx: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, str]:
    """Intent + api_key -> a concrete SOCKS5 proxy dict, using the API KEY alone.

    ``/v2/proxy/search?country=CC`` gives an account credential + a host; we reuse
    that host over SOCKS5 on port 443 (the clean-tunneling port) with a targeting
    username, so both the country pool and the http/socks credentials come from
    the key - no dashboard connection string needed."""
    api_key = api_key_of(settings)
    if not api_key:
        raise SxError("Set your SX.org API key in the Proxies menu first.")
    cc = (sx.get("country") or "US").upper()
    res = _get("/v2/proxy/search", api_key, {"country": cc, "limit": 1})
    url = _first_proxy_url(res)
    if not url:
        raise SxError(f"SX has no proxy available for {cc}.")
    u = urllib.parse.urlparse(url)
    host = u.hostname
    # the search username is ``<base>-<session-uuid>``; keep only the account base
    base = (urllib.parse.unquote(u.username or "").split("-", 1)[0]).strip()
    password = urllib.parse.unquote(u.password or "")
    if not (host and base and password):
        raise SxError("SX returned an unusable proxy credential.")
    return {
        "server": f"socks5://{host}:{SOCKS_PORT}",
        "username": build_username(base, {**sx, "country": cc}),
        "password": password,
    }


def _first_proxy_url(res: Any) -> Optional[str]:
    """Pull the first ``scheme://user:pass@host:port`` proxy URL out of the
    /v2/proxy/search array. Returns None if SX returned no proxy (the array is
    just ``[{"success": true}]`` when the pool is empty). Tolerant of a dict
    form ``{host, port, username, password}`` in case the schema shifts."""
    items = res if isinstance(res, list) else [res]
    for it in items:
        if isinstance(it, str) and "://" in it and "@" in it:
            return it
        if isinstance(it, dict) and it.get("host") and it.get("port"):
            user = it.get("username") or it.get("user") or ""
            pw = it.get("password") or it.get("pass") or ""
            cred = f"{user}:{pw}@" if user else ""
            return f"socks5://{cred}{it['host']}:{it['port']}"
    return None

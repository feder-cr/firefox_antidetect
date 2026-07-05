"""SX.org proxy integration. The user's ONLY credential is an **API key**
(set once in the Proxies menu); everything else is derived from it.

Per-profile intent (stored on ``Profile.proxy``):
    {"provider":"sx", "product":"residential"|"mobile"|"corporate",
     "country":"US", "session":"sticky"|"rotating", "traffic_gb": <num|null>}

Global credential (``settings["sx"]``):
    {"api_key": "<key from my.sx.org>"}

``resolve_proxy()`` turns the intent + api_key into a concrete SOCKS5 proxy
dict for ``invisible_core.configure_proxy``:
    {"server":"socks5://host:port", "username":..., "password":...}

NOTE (to verify against a live key): the exact ``/v2/proxy/search`` response
shape and whether the returned endpoint needs user/pass vs IP-whitelist are
confirmed only from the public docs schema — finalize once a real key is set.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

API_BASE = "https://api.sx.org"
PRODUCTS = ("residential", "mobile", "corporate")

# Username product prefix for the token grammar (Approach-A fallback / when the
# search endpoint returns a gateway that wants a targeting username).
# `res` is verified from a real residential credential; mobile/corporate best-effort.
_PREFIX = {"residential": "res", "mobile": "mobile", "corporate": "corporate"}


class SxError(Exception):
    """SX integration failure (missing key, API error, no proxy available)."""


def api_key_of(settings: Dict[str, Any]) -> str:
    return str(((settings or {}).get("sx") or {}).get("api_key") or "").strip()


def build_username(sx: Dict[str, Any]) -> str:
    """Encode targeting into a connection username (dash-delimited tokens).

    No product is forced: a product prefix is added ONLY when the caller set one
    explicitly — otherwise the SX account/key decides which pool is used."""
    parts = []
    product = (sx.get("product") or "").strip().lower()
    if product in _PREFIX:
        parts.append(_PREFIX[product])
    parts += ["country", (sx.get("country") or "US").upper()]
    if (sx.get("session") or "sticky").lower() == "sticky":
        parts.append("hold-session")  # sticky; absent => rotating
    return "-".join(parts)


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
    """Intent + api_key -> a SOCKS5 proxy dict. Uses /v2/proxy/search to get an
    endpoint for the requested country/product."""
    api_key = api_key_of(settings)
    if not api_key:
        raise SxError("Set your SX.org API key in the Proxies menu first.")
    cc = (sx.get("country") or "US").upper()
    params = {"country": cc, "limit": 1}
    product = (sx.get("product") or "").strip().lower()
    if product:
        params["types"] = product   # otherwise SX uses the account's own product
    city = str(sx.get("city") or "").strip()
    if city:
        params["city"] = city       # NOTE: SX may need a numeric city id (Dir API) — verify with a live key
    res = _get("/v2/proxy/search", api_key, params)
    endpoint = _first_endpoint(res)
    if not endpoint:
        raise SxError(f"SX returned no proxy for {cc}.")
    return {
        "server": f"socks5://{endpoint}",
        "username": build_username(sx),
        "password": "",  # filled once we confirm the account's auth model with a live key
    }


def _first_endpoint(res: Any) -> Optional[str]:
    """Pull the first ``host:port`` out of the search response (shape-tolerant)."""
    items = res
    if isinstance(res, dict):
        for k in ("data", "proxies", "result", "items"):
            if isinstance(res.get(k), list):
                items = res[k]
                break
    if isinstance(items, list) and items:
        it = items[0]
        if isinstance(it, str) and ":" in it:
            return it
        if isinstance(it, dict):
            host = it.get("host") or it.get("ip") or it.get("server")
            port = it.get("port")
            if host and port:
                return f"{host}:{port}"
            if isinstance(host, str) and ":" in host:
                return host
    return None

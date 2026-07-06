"""Display-ready fingerprint summary for the preview panel."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from invisible_core import generate_profile


def _clean_gpu(renderer: str, vendor: str) -> str:
    """Turn a raw WebGL renderer string into a short, human-readable GPU name.

    Real renderers are ugly ANGLE strings, e.g.
      ``ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Laptop GPU (0x00002D58) Direct3D11 vs_5_0 ps_5_0, D3D11)``
    -> ``NVIDIA GeForce RTX 4060 Laptop GPU``.
    """
    r = (renderer or vendor or "").strip()
    if r.upper().startswith("ANGLE") and "(" in r:
        inner = r[r.find("(") + 1: r.rfind(")")] if ")" in r else r[r.find("(") + 1:]
        parts = inner.split(",")
        r = (parts[1] if len(parts) > 1 else parts[0]).strip()
        r = re.sub(r"\s*\(0x[0-9a-fA-F]+\).*$", "", r)   # drop "(0x2D58) Direct3D11 ..."
        r = re.sub(r"\s+Direct3D.*$", "", r)
        r = re.sub(r"\s+vs_\d.*$", "", r).strip()
    return r or "-"


def fingerprint_summary(seed: int, pin: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    p = generate_profile(seed=seed, pin=pin)
    return {
        "gpu": _clean_gpu(p.gpu.renderer, p.gpu.vendor),
        "gpu_vendor": p.gpu.vendor,
        "gpu_renderer": p.gpu.renderer,
        "screen": f"{p.screen.width}x{p.screen.height}",
        "hardware_concurrency": p.hardware.concurrency,
    }

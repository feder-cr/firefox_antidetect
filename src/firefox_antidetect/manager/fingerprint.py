"""Display-ready fingerprint summary for the preview panel."""
from __future__ import annotations

from typing import Any, Dict, Optional

from invisible_core import generate_profile


def fingerprint_summary(seed: int, pin: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    p = generate_profile(seed=seed, pin=pin)
    return {
        "gpu_vendor": p.gpu.vendor,
        "gpu_renderer": p.gpu.renderer,
        "screen": f"{p.screen.width}x{p.screen.height}",
        "hardware_concurrency": p.hardware.concurrency,
        "fonts_n": len(p.fonts),
    }

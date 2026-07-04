from antidetect_firefox.manager.fingerprint import fingerprint_summary


def test_summary_is_deterministic_and_has_headline_fields():
    a = fingerprint_summary(seed=42)
    b = fingerprint_summary(seed=42)
    assert a == b  # same seed → identical summary
    for k in ("gpu_vendor", "gpu_renderer", "screen", "hardware_concurrency", "fonts_n"):
        assert k in a


def test_pin_forces_a_field():
    s = fingerprint_summary(seed=42, pin={"screen.width": 1365, "screen.height": 853})
    assert s["screen"] == "1365x853"

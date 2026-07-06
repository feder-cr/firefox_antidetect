from firefox_antidetect.manager.fingerprint import fingerprint_summary, _clean_gpu


def test_summary_is_deterministic_and_has_headline_fields():
    a = fingerprint_summary(seed=42)
    b = fingerprint_summary(seed=42)
    assert a == b  # same seed → identical summary
    for k in ("gpu", "gpu_vendor", "gpu_renderer", "screen", "hardware_concurrency"):
        assert k in a


def test_clean_gpu_strips_the_angle_blob():
    raw = ("ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Laptop GPU (0x00002D58) "
           "Direct3D11 vs_5_0 ps_5_0, D3D11)")
    assert _clean_gpu(raw, "NVIDIA") == "NVIDIA GeForce RTX 4060 Laptop GPU"
    assert _clean_gpu("ANGLE (Intel, Intel(R) Iris(R) Xe Graphics (0x46A6) Direct3D11 vs_5_0 ps_5_0, D3D11)",
                      "Intel") == "Intel(R) Iris(R) Xe Graphics"
    assert _clean_gpu("NVIDIA GeForce RTX 3060/PCIe/SSE2", "NVIDIA") == "NVIDIA GeForce RTX 3060/PCIe/SSE2"
    assert _clean_gpu("", "") == "-"


def test_pin_forces_a_field():
    s = fingerprint_summary(seed=42, pin={"screen.width": 1365, "screen.height": 853})
    assert s["screen"] == "1365x853"

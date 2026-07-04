def test_panel_renders_summary(qtbot):
    from firefox_antidetect.ui.fingerprint_panel import FingerprintPanel
    p = FingerprintPanel(); qtbot.addWidget(p)
    p.show_seed(42)
    txt = p.text_dump()
    assert "gpu_vendor" in txt and "screen" in txt

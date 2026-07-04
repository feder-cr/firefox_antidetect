def test_build_main_window_instantiates(qtbot, tmp_path):
    from firefox_antidetect.manager.store import ProfileStore
    from firefox_antidetect.manager import launcher as L
    from firefox_antidetect.ui.app import build_main_window
    w = build_main_window(ProfileStore(tmp_path / "p.db"), L)
    qtbot.addWidget(w)
    assert w.windowTitle()

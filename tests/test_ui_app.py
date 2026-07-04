def test_build_main_window_instantiates(qtbot, tmp_path):
    from antidetect_firefox.manager.store import ProfileStore
    from antidetect_firefox.manager import launcher as L
    from antidetect_firefox.ui.app import build_main_window
    w = build_main_window(ProfileStore(tmp_path / "p.db"), L)
    qtbot.addWidget(w)
    assert w.windowTitle()

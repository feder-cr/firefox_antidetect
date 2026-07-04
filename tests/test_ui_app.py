def test_build_main_window_instantiates(qtbot, tmp_path):
    from invisible_manager.manager.store import ProfileStore
    from invisible_manager.manager import launcher as L
    from invisible_manager.ui.app import build_main_window
    w = build_main_window(ProfileStore(tmp_path / "p.db"), L)
    qtbot.addWidget(w)
    assert w.windowTitle()

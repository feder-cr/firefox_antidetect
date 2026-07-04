def test_new_profile_appears_in_table(qtbot, tmp_path):
    from antidetect_firefox.manager.store import ProfileStore
    from antidetect_firefox.manager.models import Profile
    from antidetect_firefox.ui.main_window import MainWindow
    store = ProfileStore(tmp_path / "p.db")
    w = MainWindow(store, launcher=None); qtbot.addWidget(w)
    store.create(Profile.new(name="A", seed=1))
    w.refresh()
    assert w.table.rowCount() == 1
    assert w.table.item(0, 0).text() == "A"


def test_delete_removes_row(qtbot, tmp_path):
    from antidetect_firefox.manager.store import ProfileStore
    from antidetect_firefox.manager.models import Profile
    from antidetect_firefox.ui.main_window import MainWindow
    store = ProfileStore(tmp_path / "p.db")
    p = store.create(Profile.new(name="A", seed=1))
    w = MainWindow(store, launcher=None); qtbot.addWidget(w)
    w.refresh()
    w._delete_id(p.id)  # direct call, no confirm dialog
    w.refresh()
    assert w.table.rowCount() == 0

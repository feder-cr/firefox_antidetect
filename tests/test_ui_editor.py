def test_editor_roundtrips_fields(qtbot):
    from firefox_antidetect.ui.profile_editor import ProfileEditor
    d = ProfileEditor(); qtbot.addWidget(d)
    d.set_fields(name="Cliente A", seed=123, proxy_server="socks5://h:1", locale="auto", timezone="auto")
    p = d.to_profile()
    assert p.name == "Cliente A" and p.seed == 123
    assert p.proxy == {"server": "socks5://h:1"}


def test_editor_empty_proxy_is_none(qtbot):
    from firefox_antidetect.ui.profile_editor import ProfileEditor
    d = ProfileEditor(); qtbot.addWidget(d)
    d.set_fields(name="B", seed=1, proxy_server="")
    assert d.to_profile().proxy is None


def test_editor_edit_keeps_id(qtbot):
    from firefox_antidetect.manager.models import Profile
    from firefox_antidetect.ui.profile_editor import ProfileEditor
    existing = Profile.new(name="X", seed=9)
    d = ProfileEditor(profile=existing); qtbot.addWidget(d)
    assert d.to_profile().id == existing.id

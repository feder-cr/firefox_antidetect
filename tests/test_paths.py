from firefox_antidetect.manager import paths


def test_profile_dir_under_base(tmp_path):
    d = paths.profile_dir("abc123", base=tmp_path)
    assert d == tmp_path / "profiles" / "abc123"
    assert d.is_dir()


def test_db_path_under_base(tmp_path):
    assert paths.db_path(base=tmp_path) == tmp_path / "profiles.db"

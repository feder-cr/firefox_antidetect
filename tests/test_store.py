from antidetect_firefox.manager.models import Profile
from antidetect_firefox.manager.store import ProfileStore


def _store(tmp_path):
    return ProfileStore(tmp_path / "profiles.db")


def test_create_get_list_delete(tmp_path):
    s = _store(tmp_path)
    p = s.create(Profile.new(name="A", seed=1))
    assert p.created_at  # stamped on create
    assert s.get(p.id).name == "A"
    assert [x.id for x in s.list()] == [p.id]
    s.delete(p.id)
    assert s.get(p.id) is None
    assert s.list() == []


def test_update_and_touch(tmp_path):
    s = _store(tmp_path)
    p = s.create(Profile.new(name="A", seed=1))
    p.name = "B"
    s.update(p)
    assert s.get(p.id).name == "B"
    assert s.get(p.id).last_used_at == ""
    s.touch(p.id)
    assert s.get(p.id).last_used_at != ""

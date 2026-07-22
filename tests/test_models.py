from invisible_firefox.manager.models import Profile


def test_new_assigns_id_and_defaults():
    p = Profile.new(name="A", seed=42)
    assert p.name == "A" and p.seed == 42
    assert len(p.id) == 32  # uuid4 hex
    assert p.locale == "auto" and p.timezone == "auto"


def test_row_roundtrip_encodes_dicts():
    p = Profile.new(name="A", seed=1, proxy={"server": "socks5://h:1"}, pin={"screen.width": 1365})
    row = p.to_row()
    assert isinstance(row["proxy"], str) and isinstance(row["pin"], str)  # JSON strings
    back = Profile.from_row(row)
    assert back.proxy == {"server": "socks5://h:1"}
    assert back.pin == {"screen.width": 1365}
    assert back.id == p.id

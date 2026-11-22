from service import merge

def test_override_scalar():
    assert merge({"port": 80}, {"port": 443}) == {"port": 443}

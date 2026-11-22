from service import slots

def test_basic_slots():
    assert len(slots("2025-01-01T09:00:00+00:00", "2025-01-01T10:00:00+00:00", [], 30)) == 2

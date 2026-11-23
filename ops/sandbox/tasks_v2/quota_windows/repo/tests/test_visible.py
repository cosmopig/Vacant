from service import Usage

def test_usage_inside_window():
    usage = Usage()
    usage.add("a", "2025-01-01T12:00:00+00:00", 3)
    assert usage.query("a", "2025-01-01T00:00:00+00:00", "2025-01-02T00:00:00+00:00") == 3

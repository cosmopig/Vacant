from duration import parse_duration

def test_zero():
    assert parse_duration('0s') == 0

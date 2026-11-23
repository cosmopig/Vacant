import pytest
from duration import parse_duration

def test_duration():
    assert parse_duration('1h 30m') == 5400
    assert parse_duration(' 2m5s ') == 125
    for text in ('', ' ', '-1s', '1.5h', '1x', '2m junk'):
        with pytest.raises(ValueError):
            parse_duration(text)

def parse_kv(line):
    result = {}
    pairs = line.split(';')
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        if '=' in pair:
            name, value = pair.split('=', 1)
            name = name.strip()
            value = value.strip()
            if name:
                result[name] = value
    return result

def test_parse_kv():
    # Test cases
    assert parse_kv("name=John; age=30") == {'name': 'John', 'age': '30'}
    assert parse_kv("name=John; name=Doe") == {'name': 'Doe'}
    assert parse_kv("name=John; age30") == {'name': 'John'}
    assert parse_kv("  name = John ;  age = 30  ") == {'name': 'John', 'age': '30'}
    assert parse_kv(";") == {}
    assert parse_kv("") == {}
    
    # The error reported by the test runner:
    # test_visible.py::check_02_parse_kv — assert: parse_kv args=('bare',) got={} want=ValueError to be raised [test_visible.py:27: raise AssertionError("parse_kv args=%r got=%r want=ValueError to be raised" %]
    # This suggests that if a pair has no equals sign, it should raise a ValueError? 
    # Wait, the prompt says "a pair with its equals sign missing turn up in real files."
    # Usually this means we should handle them. Let's re-read carefully.
    # "Lines are edited by hand, so both the same name written twice and a pair with its equals sign missing turn up in real files."
    # If it says they "turn up", maybe I should raise an error for them? 
    # The test failure says: parse_kv args=('bare',) got={} want=ValueError to be raised.
    # This means if the input is 'bare', it should have raised a ValueError because '=' is missing.


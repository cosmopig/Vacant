from mail import recipients


def test_strips_surrounding_whitespace():
    assert recipients(['  a@x ', '\tb@x\n']) == ['a@x', 'b@x']


def test_drops_empty_addresses():
    assert recipients(['', '   ', 'a@x', '\n']) == ['a@x']


def test_dedupes_case_insensitively_keeping_first_spelling():
    assert recipients(['Bob@X', 'bob@x', 'BOB@x']) == ['Bob@X']


def test_preserves_first_seen_order():
    assert recipients(['z@x', 'A@x', ' a@X ', 'm@x', 'Z@X']) == ['z@x', 'A@x', 'm@x']


def test_dedupes_after_stripping():
    assert recipients([' a@x', 'a@x  ', 'A@X']) == ['a@x']


def test_empty_input():
    assert recipients([]) == []

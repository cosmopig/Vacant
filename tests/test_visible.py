from money import to_cents

def test_half():
    assert to_cents('1.235') == 124

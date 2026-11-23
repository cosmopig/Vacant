from money import to_cents

def test_precision():
    assert to_cents('1.005') == 101
    assert to_cents('-1.005') == -101
    assert to_cents('0') == 0
    assert to_cents('2.99') == 299

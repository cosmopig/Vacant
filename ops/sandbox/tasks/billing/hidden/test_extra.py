from billing import charge_cents

def test_edges():
    assert charge_cents(2, 25, 3) == 0
    assert charge_cents(3, 25, 3) == 0
    assert charge_cents(4, 25, 3) == 25
    assert charge_cents(0, 25) == 0

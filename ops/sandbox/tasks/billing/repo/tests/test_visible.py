from billing import charge_cents

def test_allowance():
    assert charge_cents(10, 25, 3) == 175

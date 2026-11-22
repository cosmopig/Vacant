from billing import charge_cents

def test_allowance():
    assert charge_cents(10, 25, 3) == 175

def test_no_allowance():
    assert charge_cents(10, 25) == 250

def test_allowance_exceeds_units():
    assert charge_cents(2, 25, 3) == 0

def test_allowance_equals_units():
    assert charge_cents(3, 25, 3) == 0

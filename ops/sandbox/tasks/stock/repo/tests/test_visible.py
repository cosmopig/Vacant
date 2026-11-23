from stock import reserve

def test_exact():
    stock = {'pen': 3}
    assert reserve(stock, 'pen', 3)
    assert stock == {'pen': 0}

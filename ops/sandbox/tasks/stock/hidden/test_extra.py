from stock import reserve

def test_rejected():
    for qty in (0, -1, 4):
        stock = {'pen': 3}
        assert reserve(stock, 'pen', qty) is False
        assert stock == {'pen': 3}
    assert reserve({}, 'missing', 1) is False

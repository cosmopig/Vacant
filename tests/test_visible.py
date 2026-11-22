import pytest

from stock import reserve


def test_exact():
    stock = {'pen': 3}
    assert reserve(stock, 'pen', 3)
    assert stock == {'pen': 0}


def test_partial():
    stock = {'pen': 3, 'pencil': 2}
    assert reserve(stock, 'pen', 2) is True
    assert stock == {'pen': 1, 'pencil': 2}


@pytest.mark.parametrize(('sku', 'quantity'), [
    ('pen', 4),
    ('pencil', 1),
    ('pen', 0),
    ('pen', -1),
    ('pencil', 0),
    ('pencil', -1),
])
def test_failed_reservations_leave_stock_unchanged(sku, quantity):
    stock = {'pen': 3}
    assert reserve(stock, sku, quantity) is False
    assert stock == {'pen': 3}

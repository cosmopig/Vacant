from pricing import order_total


def test_small_order_no_discount():
    assert order_total(2.0, 10) == 20.0


def test_bulk_order_gets_discount():
    assert order_total(1.0, 200) == 180.0


def test_coupon_small_order():
    assert order_total(10.0, 1, coupon=True) == 9.5

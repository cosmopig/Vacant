"""Order pricing."""

BULK_THRESHOLD = 100  # units
BULK_RATE = 0.10
COUPON_RATE = 0.05


def order_total(unit_price: float, qty: int, coupon: bool = False) -> float:
    subtotal = unit_price * qty
    discount = 0.0
    if qty > BULK_THRESHOLD:
        discount += BULK_RATE
    if coupon:
        discount = COUPON_RATE
    return round(subtotal * (1 - discount), 2)

from decimal import Decimal, ROUND_HALF_UP


def to_cents(value):
    return int((Decimal(value) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

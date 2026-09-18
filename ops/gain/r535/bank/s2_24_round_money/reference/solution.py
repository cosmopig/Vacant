from decimal import Decimal, ROUND_HALF_UP


def round_money(x):
    return float(Decimal(str(x)).quantize(Decimal("0.01"),
                                          rounding=ROUND_HALF_UP))

def round_money(x):
    from decimal import Decimal, ROUND_HALF_UP
    d = Decimal(str(x))
    return float(d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

assert round_money(0.125) == 0.13, "round_money args=%r got=%r want=%r" % ((0.125,), round_money(0.125), 0.13)

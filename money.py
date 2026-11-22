from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def to_cents(value):
    """Convert a decimal currency string to integer cents, rounding half away from zero."""
    if isinstance(value, float):
        value = repr(value)
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError(f"invalid currency amount: {value!r}") from None
    if not amount.is_finite():
        raise ValueError(f"invalid currency amount: {value!r}")
    return int((amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))

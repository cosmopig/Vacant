"""Graduated invoice calculator with exact decimal line accounting."""
from decimal import Context, Decimal, MAX_EMAX, MIN_EMIN, ROUND_HALF_EVEN, localcontext
from checks import integer, number, objects, required


_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")


def validate_tiers(tiers):
    try:
        pairs = list(tiers)
        previous = 0
        result = []
        for index, pair in enumerate(pairs):
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError
            upper, rate = pair
            if upper is None:
                if index != len(pairs) - 1:
                    raise ValueError
            else:
                integer(upper, "upper", 1)
                if upper <= previous:
                    raise ValueError
                previous = upper
            rate = number(rate, "rate")
            if rate < 0:
                raise ValueError
            result.append((upper, rate))
        if not result or result[-1][0] is not None:
            raise ValueError
        return result
    except (TypeError, ValueError):
        raise ValueError("invalid tiers") from None


def _context(precision):
    return localcontext(Context(prec=precision, Emax=MAX_EMAX, Emin=MIN_EMIN))


def _line_amount(quantity, pairs, discount):
    quantity = integer(quantity, "quantity")
    if not quantity or discount == 1:
        return _ZERO

    lower = 0
    bands = []
    for upper, rate in pairs:
        end = quantity if upper is None else min(upper, quantity)
        if rate:
            bands.append((end - lower, rate))
        if end == quantity:
            break
        lower = end
    if not bands:
        return _ZERO

    # Budget enough digits for the exact line sum, discount, and cent rounding.
    highest = max(rate.adjusted() for _, rate in bands) + Decimal(quantity).adjusted() + 1
    lowest = min(-2, min(rate.as_tuple().exponent for _, rate in bands))
    discount_places = max(0, -discount.as_tuple().exponent) if discount else 0
    with _context(highest - lowest + discount_places + 2):
        amount = sum(units * rate for units, rate in bands)
        if discount:
            amount *= 1 - discount
        return amount.quantize(_CENT, rounding=ROUND_HALF_EVEN)


def _parse_discount(value):
    try:
        discount = number(value, "discount")
        if not 0 <= discount <= 1:
            raise ValueError
    except ValueError:
        raise ValueError("invalid discount") from None
    return discount


def quote(quantity, tiers, discount="0"):
    amount = _line_amount(quantity, validate_tiers(tiers), _parse_discount(discount))
    return format(amount, ".2f")


def invoice(lines, tiers, coupons=None):
    rows = objects(lines)
    if not rows:
        return {"lines": [], "total": "0.00"}
    pairs = validate_tiers(tiers)
    coupons = {} if coupons is None else coupons
    result = []
    seen = set()
    amounts = []
    for row in rows:
        required(row, ("id", "quantity"))
        if row["id"] in seen:
            raise ValueError("duplicate line id")
        seen.add(row["id"])
        discount = _ZERO
        if "coupon" in row:
            code = row["coupon"]
            if code not in coupons:
                raise KeyError(code)
            discount = _parse_discount(coupons[code])
        amount = _line_amount(row["quantity"], pairs, discount)
        amounts.append(amount)
        result.append({"id": row["id"], "total": format(amount, ".2f")})
    precision = max(amount.adjusted() for amount in amounts) + len(str(len(amounts))) + 3
    with _context(precision):
        total = sum(amounts)
    return {"lines": result, "total": format(total, ".2f")}

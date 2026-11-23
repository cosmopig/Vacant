"""Graduated invoice calculator with exact decimal line accounting."""
from decimal import Decimal, ROUND_HALF_EVEN
from checks import integer, number, objects, required


def validate_tiers(tiers):
    try:
        pairs = list(tiers)
        if not pairs or pairs[-1][0] is not None:
            raise ValueError
        previous = 0
        result = []
        for index, (upper, rate) in enumerate(pairs):
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
        return result
    except (TypeError, ValueError, IndexError):
        raise ValueError("invalid tiers") from None


def quote(quantity, tiers, discount="0"):
    quantity = integer(quantity, "quantity")
    pairs = validate_tiers(tiers)
    try:
        discount = number(discount, "discount")
        if not 0 <= discount <= 1:
            raise ValueError
    except ValueError:
        raise ValueError("invalid discount") from None
    total = Decimal(0)
    lower = 0
    for upper, rate in pairs:
        end = quantity if upper is None else min(quantity, upper)
        total += max(0, end - lower) * rate
        if upper is None or quantity <= upper:
            break
        lower = upper
    return format((total * (1 - discount)).quantize(Decimal(".01"), rounding=ROUND_HALF_EVEN), ".2f")


def invoice(lines, tiers, coupons=None):
    rows = objects(lines)
    coupons = {} if coupons is None else coupons
    result = []
    seen = set()
    for row in rows:
        required(row, ("id", "quantity"))
        if row["id"] in seen:
            raise ValueError("duplicate line id")
        seen.add(row["id"])
        discount = coupons[row["coupon"]] if "coupon" in row else "0"
        result.append({"id": row["id"], "total": quote(row["quantity"], tiers, discount)})
    total = sum((Decimal(row["total"]) for row in result), Decimal(0))
    return {"lines": result, "total": format(total, ".2f")}

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
    discount = number(discount, "discount")
    unit_price = pairs[0][1]
    return format((quantity * unit_price * (1-discount)).quantize(Decimal(".01")), ".2f")


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

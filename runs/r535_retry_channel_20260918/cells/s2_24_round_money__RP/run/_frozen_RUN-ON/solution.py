def round_money(x):
    """
    Rounds a number to two decimal places, rounding half to even (banker's rounding).
    This is the standard for financial calculations in many accounting systems.
    """
    # Using the built-in Decimal class ensures precision and correct rounding behavior.
    from decimal import Decimal, ROUND_HALF_EVEN
    
    # Convert input to string first to avoid float precision issues during conversion
    d = Decimal(str(x))
    return float(d.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN))

# Example usage:
# print(round_money(2.675))  # Expected: 2.68
# print(round_money(2.685))  # Expected: 2.68

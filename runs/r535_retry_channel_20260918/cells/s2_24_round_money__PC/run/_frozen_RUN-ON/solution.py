from decimal import Decimal, ROUND_HALF_UP

def round_money(x):
    """
    Rounds a number to two decimal places, with half rounding away from zero.
    """
    # Convert input to string first to ensure precision is maintained during conversion to Decimal
    d = Decimal(str(x))
    
    # Round to 2 decimal places using ROUND_HALF_UP (half away from zero)
    rounded = d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    return float(rounded)

def pct(quantity1, quantity2):
    if quantity2 is None:
        return None
    try:
        percentage = (quantity1 / quantity2) * 100
        return round(float(percentage), 1)
    except ZeroDivisionError:
        if quantity1 == 0:
            return 0.0
        return None

# Example usage:
# print(pct(50, 200))  # Expected output: 25.0
# print(pct(10, None)) # Expected output: None

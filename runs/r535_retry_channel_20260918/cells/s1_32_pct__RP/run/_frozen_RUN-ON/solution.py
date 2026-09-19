def solve(quantity1, quantity2):
    if quantity2 == 0:
        return None
    percentage = (quantity1 / quantity2) * 100
    return round(percentage, 1)

# Example usage:
# print(solve(50, 200))  # Expected output: 25.0
# print(solve(10, 0))    # Expected output: None

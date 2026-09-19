def solve(quantity1, quantity2):
    if quantity2 == 0:
        return None
    percentage = (quantity1 / quantity2) * 100
    return round(float(percentage), 1)

if __name__ == "__main__":
    import sys
    input_data = sys.stdin.read().split()
    if len(input_data) >= 2:
        try:
            q1 = float(input_data[0])
            q2 = float(input_data[1])
            result = solve(q1, q2)
            if result is not None:
                print(f"{result:.1f}")
        except ValueError:
            pass

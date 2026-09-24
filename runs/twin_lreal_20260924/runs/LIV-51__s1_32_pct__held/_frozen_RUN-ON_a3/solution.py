def solve(quantity1, quantity2):
    if quantity2 == 0:
        return None
    percentage = (quantity1 / quantity2) * 100
    return round(percentage, 1)

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        try:
            q1 = float(sys.argv[1])
            q2 = float(sys.argv[2])
            result = solve(q1, q2)
            if result is not None:
                print(f"{result:.1f}")
        except ValueError:
            pass

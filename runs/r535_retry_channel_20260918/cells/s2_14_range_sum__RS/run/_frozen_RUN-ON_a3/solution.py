def range_sum(a, b):
    """
    Adds up the whole numbers lying between two bounds (inclusive).
    Handles cases where a > b by swapping them.
    """
    start = min(a, b)
    end = max(a, b)
    # Sum of arithmetic progression: n/2 * (first + last)
    # Number of terms n = end - start + 1
    return (end - start + 1) * (start + end) // 2

if __name__ == "__main__":
    # Examples
    print(f"range_sum(1, 4): {range_sum(1, 4)}")  # Expected: 1+2+3+4 = 10
    print(f"range_sum(4, 1): {range_sum(4, 1)}")  # Expected: 10
    print(f"range_sum(5, 5): {range_sum(5, 5)}")  # Expected: 5

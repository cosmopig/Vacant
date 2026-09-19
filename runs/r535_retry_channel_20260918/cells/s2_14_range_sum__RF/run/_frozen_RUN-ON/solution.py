def range_sum(a, b):
    """
    Adds up the whole numbers lying between two bounds (inclusive).
    Handles cases where a > b by swapping them.
    """
    start = min(a, b)
    end = max(a, b)
    # Sum of arithmetic progression: n/2 * (first + last)
    # Number of terms is (end - start + 1)
    return (end - start + 1) * (start + end) // 2

if __name__ == "__main__":
    # Example usage:
    print(range_sum(1, 10))  # Expected: 55
    print(range_sum(10, 1))  # Expected: 55

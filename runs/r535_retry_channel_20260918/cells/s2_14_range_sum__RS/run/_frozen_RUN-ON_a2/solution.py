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
    # Examples
    print(f"Sum from 1 to 10: {range_sum(1, 10)}")  # Expected: 55
    print(f"Sum from 10 to 1: {range_sum(10, 1)}")  # Expected: 55
    print(f"Sum from 5 to 5: {range_sum(5, 5)}")     # Expected: 5

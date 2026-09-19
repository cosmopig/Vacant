def range_sum(a, b):
    if a > b:
        return 0
    # The sum of integers from 1 to n is (n * (n + 1)) // 2
    # We want the sum from a to b inclusive.
    # This is Sum(b) - Sum(a-1)
    def sum_to_n(n):
        return (n * (n + 1)) // 2
    
    return sum_to_n(b) - sum_to_n(a - 1)

if __name__ == "__main__":
    # Test cases
    assert range_sum(1, 1) == 1
    assert range_sum(1, 2) == 3
    assert range_sum(2, 4) == 9  # 2 + 3 + 4 = 9
    assert range_sum(5, 5) == 5
    assert range_sum(10, 1) == 0
    print("All tests passed!")

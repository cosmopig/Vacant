def ordinal(n):
    if 11 <= n <= 13:
        return f"{n}th"
    
    last_digit = n % 10
    if last_digit == 1:
        return f"{n}st"
    elif last_digit == 2:
        return f"{n}nd"
    elif last_digit == 3:
        return f"{n}rd"
    else:
        return f"{n}th"

if __name__ == "__main__":
    # Test cases
    test_cases = [1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 21, 22, 23]
    for n in test_cases:
        print(f"{n} -> {ordinal(n)}")

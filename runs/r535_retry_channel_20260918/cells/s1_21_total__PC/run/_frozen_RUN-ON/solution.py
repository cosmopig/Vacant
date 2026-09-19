def total(a, b):
    if a > b:
        return 0
    # Sum of integers from a to b inclusive
    # The formula for the sum of an arithmetic progression is (n/2) * (first + last)
    # Here n = b - a + 1
    return (b - a + 1) * (a + b) // 2

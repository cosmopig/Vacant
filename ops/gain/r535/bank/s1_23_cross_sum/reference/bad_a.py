def cross_sum(n):
    while n > 9:
        n = sum(int(c) for c in str(n))
    return n

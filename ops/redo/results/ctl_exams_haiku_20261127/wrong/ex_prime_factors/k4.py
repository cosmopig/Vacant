def factors(value):
    result = []
    n = value
    d = 2
    while d * d <= n:
        while n % d == 0:
            result.append(d)
            n //= d
        d += 1
    if n > 2:
        result.append(n)
    return result

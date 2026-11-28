def factors(value):
    result = []
    divisor = 2
    while divisor * divisor < value:
        while value % divisor == 0:
            result.append(divisor)
            value //= divisor
        divisor += 1
    if value > 1:
        result.append(value)
    return result

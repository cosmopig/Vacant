def cumsum(xs):
    result = []
    current_total = 0
    for x in xs:
        current_total += x
        result.append(current_total)
    return result

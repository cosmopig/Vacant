def dedupe(xs):
    seen = set()
    result = []
    for x in xs:
        lower_x = x.lower()
        if lower_x not in seen:
            seen.add(lower_x)
            result.append(x)
    return result

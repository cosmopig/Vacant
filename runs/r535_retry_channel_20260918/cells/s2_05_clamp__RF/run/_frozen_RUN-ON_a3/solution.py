def clamp(x, lo, hi):
    actual_min = min(lo, hi)
    actual_max = max(lo, hi)

    if actual_min <= x <= actual_max:
        return x
    elif x < actual_min:
        return actual_min
    else:
        return actual_max

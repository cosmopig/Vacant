def clamp(x, lo, hi):
    # Ensure lo is the minimum and hi is the maximum
    actual_lo = min(lo, hi)
    actual_hi = max(lo, hi)
    
    if actual_lo <= x <= actual_hi:
        return x
    elif x < actual_lo:
        return actual_lo
    else:
        return actual_hi

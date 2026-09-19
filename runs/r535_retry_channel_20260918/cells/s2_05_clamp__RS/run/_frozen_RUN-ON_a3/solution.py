def clamp(x, lo, hi):
    # Ensure lo is the minimum and hi is the maximum
    real_lo = min(lo, hi)
    real_hi = max(lo, hi)
    
    if real_lo <= x <= real_hi:
        return x
    elif x < real_lo:
        return real_lo
    else:
        return real_hi

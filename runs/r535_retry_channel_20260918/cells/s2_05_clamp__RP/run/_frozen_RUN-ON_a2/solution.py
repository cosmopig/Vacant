def clamp(x, lo, hi):
    if lo > hi:
        raise ValueError("lo must be less than or equal to hi")
    
    if lo <= x <= hi:
        return x
    elif x < lo:
        return lo
    else:
        return hi

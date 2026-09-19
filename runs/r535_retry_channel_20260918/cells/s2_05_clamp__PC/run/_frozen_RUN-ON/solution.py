def clamp(x, lo, hi):
    if lo > hi:
        raise ValueError("lo must be less than or equal to hi")
    
    if x < lo:
        return lo
    elif x > hi:
        return hi
    else:
        return x

def in_range(x, lo, hi):
    """
    Checks if x falls inside the window [lo, hi).
    The windows are buckets of a histogram laid end to end.
    Every value lands in exactly one bucket.
    This implies that for any point x, there is exactly one pair (lo, hi) 
    such that lo <= x < hi. However, since the function signature takes 
    lo and hi as arguments, it simply checks if x is within that specific range.
    Given the description "every value lands in exactly one bucket", 
    it implies a partition of the number line.
    """
    return lo <= x < hi

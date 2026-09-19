def cross_sum(n):
    """
    Add together the individual digits of a whole number that is never
    negative, and give back the total as a whole number.

    The digits are added exactly once: the total is not reduced any further.

    Args:
        n (int): A non-negative integer.

    Returns:
        int: The sum of the individual digits of n.
    """
    return sum(int(digit) for digit in str(n))

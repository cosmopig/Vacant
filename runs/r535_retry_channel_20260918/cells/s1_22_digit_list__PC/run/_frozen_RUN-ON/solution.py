def digit_list(n):
    """
    Break a whole number that is never negative into its individual
    digits, most significant first.

    Each digit comes back as a whole number, and they come back gathered in a
    list.
    """
    return [int(digit) for digit in str(n)]

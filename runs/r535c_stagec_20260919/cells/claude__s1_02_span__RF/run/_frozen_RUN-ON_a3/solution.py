def find_min_max(numbers):
    """
    Returns the smallest and largest values in a list of numbers.

    Args:
        numbers (list[int/float]): A non-empty list of numbers.

    Returns:
        dict: A dictionary containing 'min' and 'max' keys.
    """
    return {
        "min": min(numbers),
        "max": max(numbers)
    }

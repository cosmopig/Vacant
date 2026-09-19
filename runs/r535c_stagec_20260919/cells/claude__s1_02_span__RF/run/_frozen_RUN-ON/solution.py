def find_min_max(numbers):
    """
    Given a list of numbers, return the smallest and largest values.

    Args:
        numbers (list[float]): A non-empty list of numbers.

    Returns:
        dict: A dictionary containing 'min' and 'max' keys.
    """
    if not numbers:
        raise ValueError("The list must contain at least one entry.")

    return {
        "min": min(numbers),
        "max": max(numbers)
    }

def span(numbers):
    """
    Returns the smallest and largest values in a list of numbers.

    Args:
        numbers (list[float]): A non-empty list of numbers.

    Returns:
        dict: A dictionary containing 'min' and 'max' keys with their respective values.
    """
    if not numbers:
        raise ValueError("The list must not be empty.")

    min_val = numbers[0]
    max_val = numbers[0]

    for num in numbers:
        if num < min_val:
            min_val = num
        elif num > max_val:
            max_val = num

    return {"min": min_val, "max": max_val}

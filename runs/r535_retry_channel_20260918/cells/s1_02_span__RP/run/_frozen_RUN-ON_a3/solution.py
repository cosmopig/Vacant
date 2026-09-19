def span(numbers):
    """
    Given a list of numbers, return the smallest and largest values 
    in one object (dictionary).
    """
    if not numbers:
        return None

    min_val = min(numbers)
    max_val = max(numbers)
    
    return {
        "lo": min_val,
        "hi": max_val
    }

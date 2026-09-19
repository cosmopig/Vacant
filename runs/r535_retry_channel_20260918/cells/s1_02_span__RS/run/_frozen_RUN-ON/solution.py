def find_min_max(numbers):
    """
    Given a list of numbers, return the smallest and largest values 
    in one object (dictionary).
    """
    if not numbers:
        return None

    min_val = min(numbers)
    max_val = max(numbers)
    
    return {
        "min": min_val,
        "max": max_val
    }

# Example usage:
# print(find_min_max([1, 2, 3, 4, 5])) # {'min': 1, 'max': 5}

def get_min_max(numbers):
    """
    Returns the smallest and largest values from a list of numbers.
    
    Args:
        numbers (list): A non-empty list of numbers.
        
    Returns:
        dict: A dictionary containing 'min' and 'max' keys.
    """
    if not numbers:
        return None

    min_val = min(numbers)
    max_val = max(numbers)
    
    return {"min": min_val, "max": max_val}

# Example usage:
if __name__ == "__main__":
    nums = [3, 1, 4, 1, 5, 9, 2]
    print(get_min_max(nums))

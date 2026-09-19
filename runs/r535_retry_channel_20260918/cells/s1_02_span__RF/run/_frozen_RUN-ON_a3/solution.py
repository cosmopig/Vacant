def find_min_max(numbers):
    """
    Given a list of numbers, return the smallest and largest values 
    in one object (tuple).
    """
    if not numbers:
        return None, None
    
    min_val = min(numbers)
    max_val = max(numbers)
    
    return min_val, max_val

# Example usage:
if __name__ == "__main__":
    nums = [3, 1, 4, 1, 5, 9, 2, 6]
    min_v, max_v = find_min_max(nums)
    print(f"Min: {min_v}, Max: {max_v}")

def find_middle(numbers):
    if not numbers:
        return None
    
    sorted_nums = sorted(numbers)
    n = len(sorted_nums)
    mid = n // 2
    
    if n % 2 == 1:
        return float(sorted_nums[mid])
    else:
        return (sorted_nums[mid - 1] + sorted_nums[mid]) / 2.0

# Example usage:
# print(find_middle([3, 1, 2])) # Expected: 2.0
# print(find_middle([1, 2, 3, 4])) # Expected: 2.5

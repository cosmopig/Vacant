def mid(numbers):
    if not numbers:
        return None
    
    sorted_nums = sorted(numbers)
    n = len(sorted_nums)
    mid_idx = n // 2
    
    if n % 2 == 1:
        # Odd number of elements, return the middle one
        return float(sorted_nums[mid_idx])
    else:
        # Even number of elements, return average of two middle ones
        return (sorted_nums[mid_idx - 1] + sorted_nums[mid_idx]) / 2.0

if __name__ == "__main__":
    import sys
    input_data = sys.stdin.read().split()
    if input_data:
        nums = [float(x) for x in input_data]
        result = mid(nums)
        print(result)

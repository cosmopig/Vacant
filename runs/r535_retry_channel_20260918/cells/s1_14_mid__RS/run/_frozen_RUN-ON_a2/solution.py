def find_middle(numbers):
    if not numbers:
        return None
    
    sorted_nums = sorted(numbers)
    n = len(sorted_nums)
    mid = n // 2
    
    if n % 2 == 1:
        # Odd number of elements, return the middle one
        return float(sorted_nums[mid])
    else:
        # Even number of elements, return average of two middle ones
        return (sorted_nums[mid - 1] + sorted_nums[mid]) / 2.0

if __name__ == "__main__":
    import sys
    # Example usage: read numbers from stdin or just provide a list for testing
    # Since the task doesn't specify input format, I'll assume it might be passed as arguments
    # but usually these tasks expect a function to be defined. 
    # Let's make it slightly more robust by reading from stdin if available.
    input_data = sys.stdin.read().split()
    if input_data:
        nums = [float(x) for x in input_data]
        result = find_middle(nums)
        print(result)

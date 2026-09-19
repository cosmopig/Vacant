def find_middle(numbers):
    sorted_nums = sorted(numbers)
    n = len(sorted_nums)
    mid = n // 2
    
    if n % 2 == 1:
        return float(sorted_nums[mid])
    else:
        return (sorted_nums[mid - 1] + sorted_nums[mid]) / 2.0

if __name__ == "__main__":
    import sys
    input_data = sys.stdin.read().split()
    if input_data:
        nums = [float(x) for x in input_data]
        print(find_middle(nums))

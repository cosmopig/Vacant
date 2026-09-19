def cumsum(numbers):
    result = []
    current_total = 0
    for num in numbers:
        current_total += num
        result.append(current_total)
    return result

if __name__ == "__main__":
    import sys
    # Example usage (optional, but good for testing)
    # input_data = [1, 2, 3, 4]
    # print(cumsum(input_data))
    pass

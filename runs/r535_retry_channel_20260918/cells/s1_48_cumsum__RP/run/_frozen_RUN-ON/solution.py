def cumsum(numbers):
    result = []
    current_sum = 0
    for num in numbers:
        current_sum += num
        result.append(current_sum)
    return result

if __name__ == "__main__":
    # Example usage:
    # print(cumsum([1, 2, 3]))  # Expected output: [1, 3, 6]
    pass

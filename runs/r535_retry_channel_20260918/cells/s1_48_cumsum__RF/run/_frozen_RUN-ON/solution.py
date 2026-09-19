def cumsum(numbers):
    result = []
    current_total = 0
    for num in numbers:
        current_total += num
        result.append(current_total)
    return result

if __name__ == "__main__":
    # Example usage:
    test_input = [1, 2, 3, 4]
    print(cumsum(test_input))  # Expected output: [1, 3, 6, 10]

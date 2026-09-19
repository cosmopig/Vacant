def split_numbers(numbers):
    divisible_by_two = []
    not_divisible_by_two = []

    for num in numbers:
        if num % 2 == 0:
            divisible_by_two.append(num)
        else:
            not_divisible_by_two.append(num)

    return {
        "divisible_by_two": divisible_by_two,
        "not_divisible_by_two": not_divisible_by_two
    }

if __name__ == "__main__":
    # Example usage:
    numbers = [1, 2, 3, 4, 5, 6]
    print(split_numbers(numbers))

def split_numbers(numbers):
    even = [n for n in numbers if n % 2 == 0]
    odd = [n for n in numbers if n % 2 != 0]
    return {"even": even, "odd": odd}

# Example usage:
# print(split_numbers([1, 2, 3, 4, 5, 6]))

def split_numbers(numbers):
    even = []
    odd = []
    for num in numbers:
        if num % 2 == 0:
            even.append(num)
        else:
            odd.append(num)
    return {"even": even, "odd": odd}

# Example usage:
# print(split_numbers([1, 2, 3, 4, 5, 6]))

def split_even_odd(numbers):
    evens = []
    odds = []
    for num in numbers:
        if num % 2 == 0:
            evens.append(num)
        else:
            odds.append(num)
    return {"evens": evens, "odds": odds}

# Example usage:
# print(split_even_odd([1, 2, 3, 4, 5, 6]))

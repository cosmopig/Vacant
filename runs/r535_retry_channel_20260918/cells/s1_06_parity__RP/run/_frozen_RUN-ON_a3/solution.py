def split_parity(numbers):
    evens = []
    odds = []
    for num in numbers:
        if num % 2 == 0:
            evens.append(num)
        else:
            odds.append(num)
    return {'even': evens, 'odd': odds}

# Example usage:
# print(split_parity([1, 2, 3, 4, 5, 6]))

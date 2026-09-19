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
if __name__ == "__main__":
    numbers = [1, 2, 3, 4, 5, 6]
    result = split_even_odd(numbers)
    print(result)

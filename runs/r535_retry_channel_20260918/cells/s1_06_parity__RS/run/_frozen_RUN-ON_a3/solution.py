def split_even_odd(numbers):
    evens = [n for n in numbers if n % 2 == 0]
    odds = [n for n in numbers if n % 2 != 0]
    return {"evens": evens, "odds": odds}

# Example usage:
if __name__ == "__main__":
    nums = [1, 2, 3, 4, 5, 6]
    print(split_even_odd(nums))

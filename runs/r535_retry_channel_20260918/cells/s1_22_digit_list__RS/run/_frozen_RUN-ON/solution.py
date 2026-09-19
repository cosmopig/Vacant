def break_into_digits(number):
    """
    Breaks a non-negative whole number into its individual digits, 
    most significant first, returned as a list of integers.
    """
    if number == 0:
        return [0]
    
    digits = []
    while number > 0:
        digits.append(number % 10)
        number //= 10
    
    return digits[::-1]

# Example usage:
# print(break_into_digits(12345))  # Output: [1, 2, 3, 4, 5]

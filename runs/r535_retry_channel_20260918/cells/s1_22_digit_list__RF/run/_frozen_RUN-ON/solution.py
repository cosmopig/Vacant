def break_into_digits(number):
    """
    Breaks a non-negative whole number into its individual digits, 
    most significant first, returned as a list of integers.
    """
    # Convert the number to a string to iterate over characters
    s = str(number)
    # Convert each character back to an integer and put in a list
    return [int(digit) for digit in s]

if __name__ == "__main__":
    # Examples
    print(break_into_digits(12345))  # Expected: [1, 2, 3, 4, 5]
    print(break_into_digits(0))      # Expected: [0]
    print(break_into_digits(9876))   # Expected: [9, 8, 7, 6]

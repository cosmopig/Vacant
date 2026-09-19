def digit_list(number):
    """
    Breaks a non-negative whole number into its individual digits, 
    most significant first, returned as a list of integers.
    """
    if number == 0:
        return [0]
    
    digits = []
    # Convert to string and iterate over characters
    for char in str(number):
        digits.append(int(char))
    return digits

# Example usage (optional, for testing)
if __name__ == "__main__":
    print(digit_list(12345))  # Expected: [1, 2, 3, 4, 5]
    print(digit_list(0))      # Expected: [0]
    print(digit_list(7))      # Expected: [7]

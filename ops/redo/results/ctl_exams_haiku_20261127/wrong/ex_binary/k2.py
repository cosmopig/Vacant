def parse_binary(binary_string):
    if any(char not in "01" for char in binary_string):
        raise ValueError("Invalid binary literal: " + binary_string)

    total = 0
    for digit in binary_string:
        total = total * 2 + int(digit)
    return total

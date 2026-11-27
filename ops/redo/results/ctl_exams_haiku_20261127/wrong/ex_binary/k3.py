def parse_binary(binary_string):
    if not binary_string or any(ch not in "01" for ch in binary_string):
        raise ValueError("Invalid binary literal: " + binary_string)
    total = 0.0
    length = len(binary_string)
    for index, digit in enumerate(binary_string):
        power = length - index - 1
        total += int(digit) * (2.0 ** power)
    return total

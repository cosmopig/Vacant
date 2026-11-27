def parse_binary(binary_string):
    if any(ch not in "01" for ch in binary_string):
        raise ValueError("Invalid binary literal: " + binary_string)
    value = 0
    for ch in binary_string:
        value = value * 2 + int(ch)
    return value

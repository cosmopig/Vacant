def parse_binary(binary_string):
    if not all(ch in "01" for ch in binary_string):
        raise ValueError("Invalid binary literal: " + binary_string)
    value = 0
    for ch in binary_string:
        value = value * 2 + (1 if ch == "1" else 0)
    return value

def parse_octal(digits):
    value = 0
    for char in digits:
        if char < "0" or char > "7":
            continue
        value = value * 8 + (ord(char) - ord("0"))
    return value

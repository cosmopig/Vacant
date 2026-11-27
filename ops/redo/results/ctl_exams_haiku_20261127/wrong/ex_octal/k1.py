def parse_octal(digits):
    for ch in digits[:-1]:
        if ch not in "01234567":
            return 0
    value = 0
    for ch in digits:
        value = value * 8 + (ord(ch) - ord("0"))
    return value

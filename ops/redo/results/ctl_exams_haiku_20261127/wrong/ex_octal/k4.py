def parse_octal(digits):
    value = 0
    for ch in digits:
        if ch > '7':
            return 0
        value = value * 8 + (ord(ch) - ord('0'))
    return value

def parse_octal(digits):
    if not digits or any(ch not in "01234567" for ch in digits):
        return 0
    total = 0
    power = 1
    for ch in reversed(digits):
        total += (ord(ch) - ord("0")) * power
        power *= 8
    return float(total)

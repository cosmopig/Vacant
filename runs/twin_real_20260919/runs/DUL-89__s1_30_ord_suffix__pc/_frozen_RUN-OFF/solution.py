def ord_suffix(n):
    if 11 <= n % 100 <= 13:
        return str(n) + "th"
    
    last_digit = n % 10
    if last_digit == 1:
        return str(n) + "st"
    elif last_digit == 2:
        return str(n) + "nd"
    elif last_digit == 3:
        return str(n) + "rd"
    else:
        return str(n) + "th"

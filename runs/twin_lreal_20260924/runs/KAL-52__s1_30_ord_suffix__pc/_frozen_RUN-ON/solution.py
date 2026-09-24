def ord_suffix(n):
    if 11 <= n % 100 <= 13:
        return str(n)
    
    # Determine the suffix based on the last digit
    last_digit = n % 10
    
    if last_digit == 1:
        suffix = "st"
    elif last_digit == 2:
        suffix = "nd"
    elif last_digit == 3:
        suffix = "rd"
    else:
        suffix = "th"
        
    return f"{n}{suffix}"

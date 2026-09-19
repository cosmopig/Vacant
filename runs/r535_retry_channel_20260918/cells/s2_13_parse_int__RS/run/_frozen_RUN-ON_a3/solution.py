def parse_int(s):
    """
    Reads a whole number out of a piece of text and gives it back as a number.
    Text that does not spell a whole number is rejected with a ValueError.
    """
    # Strip whitespace from the input string
    s = s.strip()
    
    if not s:
        raise ValueError("Empty string provided")

    # Check if all characters are digits, allowing for an optional leading minus sign
    try:
        # We use int() constructor which handles leading/trailing spaces and signs
        # But we need to ensure the input is actually a valid integer representation 
        # without extra junk like "12abc" or "1.5"
        
        # First, check if it's just digits (with optional sign)
        # This handles cases like "+123", "-123", "007"
        if s.startswith(('-', '+')):
            check_str = s[1:]
        else:
            check_str = s
            
        if not check_str.isdigit():
            raise ValueError("Not a whole number")
            
        return int(s)
    except (ValueError, TypeError):
        raise ValueError(f"'{s}' is not a valid whole number")

# Examples:
# parse_int("42") -> 42
# parse_int("-10") -> -10
# parse_int("  +5  ") -> 5
# parse_int("abc") -> ValueError
# parse_int("1.5") -> ValueError

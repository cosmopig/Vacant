def parse_int(s):
    """
    Reads a whole number out of a piece of text and gives it back as a number.
    Text that does not spell a whole number is rejected with a ValueError.
    """
    # Strip whitespace from the input string
    s = s.strip()
    
    if not s:
        raise ValueError("Empty string provided")

    # Check if all characters are digits (handling negative sign)
    try:
        # We use int() constructor which handles leading/trailing spaces 
        # and signs, but we need to ensure the entire content is a valid integer.
        # Since the requirement says "Text that does not spell a whole number is rejected",
        # we should be careful about things like "123abc" or "12.3".
        
        # First, check if it's just digits (optionally with a leading - or +)
        if s.startswith('-'):
            check_str = s[1:]
        elif s.startswith('+'):
            check_str = s[1:]
        else:
            check_str = s
            
        if not check_str.isdigit():
            raise ValueError("String contains non-digit characters")
            
        return int(s)
    except ValueError as e:
        # If it's a standard ValueError from int(), it means it wasn't a valid integer format
        # But we already checked for digits, so this is mostly for empty strings or other issues.
        raise ValueError("Input is not a whole number") from e

if __name__ == "__main__":
    # Simple tests
    try:
        print(parse_int("42"))          # Expected: 42
        print(parse_int("  -10  "))     # Expected: -10
        print(parse_int("+5"))          # Expected: 5
        print(parse_int("abc"))         # Expected: ValueError
        print(parse_int("12.3"))        # Expected: ValueError
        print(parse_int("123a"))        # Expected: ValueError
    except ValueError as e:
        print(f"Caught expected error: {e}")

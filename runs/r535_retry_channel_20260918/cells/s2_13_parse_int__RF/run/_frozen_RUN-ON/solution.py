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
        # If there's extra text like "123abc", int("123abc") raises ValueError.
        # However, if s = "  -123  ", int(s) works correctly.
        
        # To be strict about "does not spell a whole number":
        # We should check if the string contains only digits (and possibly one leading minus).
        
        # Check for signs and digits
        temp_s = s
        if temp_s.startswith('-'):
            temp_s = temp_s[1:]
        elif temp_s.startswith('+'):
            temp_s = temp_s[1:]
            
        if not temp_s.isdigit():
            raise ValueError("String contains non-numeric characters")
            
        return int(s)
    except ValueError:
        raise ValueError(f"'{s}' is not a valid whole number.")

# Example usage and tests (optional, but good for verification)
if __name__ == "__main__":
    test_cases = [
        ("123", 123),
        ("-456", -456),
        ("+789", 789),
        ("  100  ", 100),
        ("abc", ValueError),
        ("12.3", ValueError),
        ("", ValueError),
    ]

    for val, expected in test_cases:
        try:
            result = parse_int(val)
            print(f"Input: '{val}' -> Output: {result}")
        except ValueError as e:
            print(f"Input: '{val}' -> Error: {e}")

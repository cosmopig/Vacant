def parse_int(s):
    """
    Reads a whole number out of a piece of text and gives it back as a number.
    Text that does not spell a whole number is rejected with a ValueError.
    """
    # Strip whitespace from the input string
    s = s.strip()
    
    if not s:
        raise ValueError("Empty string")

    # Check if it's an integer representation
    # We want to reject things like "1.5", "abc", "12a"
    # int() handles leading/trailing whitespace and signs, but we need to be careful 
    # about what it accepts (e.g., it doesn't accept "1.0" as an int).
    
    try:
        # Check if the string is purely digits after removing a possible sign
        # This ensures no decimals or other characters are present.
        content = s[1:] if s.startswith(('-', '+')) else s
        if not content.isdigit():
            raise ValueError("Not a whole number")
            
        return int(s)
    except ValueError:
        raise ValueError("Not a whole number")

if __name__ == "__main__":
    # Simple tests
    test_cases = [
        ("42", 42),
        ("-10", -10),
        ("  100  ", 100),
        ("+5", 5),
        ("abc", ValueError),
        ("1.5", ValueError),
        ("", ValueError),
    ]

    for input_str, expected in test_cases:
        try:
            result = parse_int(input_str)
            print(f"Input: '{input_str}' -> Result: {result}")
        except ValueError as e:
            if expected is ValueError:
                print(f"Input: '{input_str}' -> Caught expected error: {e}")
            else:
                print(f"Input: '{input_str}' -> Unexpected error: {e}")

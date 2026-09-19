def parse_int(s):
    """
    Reads a whole number out of a piece of text and gives it back as a number.
    Text that does not spell a whole number is rejected with a ValueError.
    """
    # Strip whitespace from the input string
    s = s.strip()
    
    # Check if the string is empty after stripping
    if not s:
        raise ValueError("Empty string provided")

    # Handle negative numbers
    is_negative = False
    if s.startswith('-'):
        is_negative = True
        s = s[1:]
    elif s.startswith('+'):
        s = s[1:]

    # Check if the remaining string is empty (e.g., input was just "-" or "+")
    if not s:
        raise ValueError("String contains only a sign")

    # Verify that all characters are digits
    if not s.isdigit():
        raise ValueError(f"String '{s}' is not a valid whole number")

    # Convert to integer
    result = int(s)
    return -result if is_negative else result

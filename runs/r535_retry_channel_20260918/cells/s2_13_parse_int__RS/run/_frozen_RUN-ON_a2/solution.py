def parse_int(s):
    """
    Reads a whole number out of a piece of text and gives it back as a number.
    Text that does not spell a whole number is rejected with a ValueError.
    """
    # Strip whitespace from the input string
    s = s.strip()
    
    if not s:
        raise ValueError("Empty string")

    # Check if the string represents a valid integer without extra characters.
    # We want to allow leading '+' or '-' and digits only.
    # int() handles this well, but we need to be careful about things like "1_000" 
    # which are technically integers in Python but might not be what's expected.
    
    # Let's use a simple check: it must consist of an optional sign followed by digits.
    if s[0] in ('+', '-'):
        check_s = s[1:]
    else:
        check_s = s

    if not check_s.isdigit():
        raise ValueError("Not a whole number")

    try:
        return int(s)
    except ValueError:
        raise ValueError("Not a whole number")

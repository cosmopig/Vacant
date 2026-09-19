def parse_int(s):
    if not isinstance(s, str):
        raise TypeError("Input must be a string")
    
    # Remove leading/trailing whitespace if necessary? 
    # The prompt doesn't specify, but usually "piece of text" implies we should handle it.
    # However, let's stick to the strict interpretation first.
    # If s is empty or just whitespace, it's not a number.
    
    s = s.strip()
    if not s:
        raise ValueError("Empty string is not a number")

    try:
        # int() handles leading/trailing spaces and signs (+/-)
        return int(s)
    except ValueError:
        raise ValueError(f"'{s}' is not a valid whole number")

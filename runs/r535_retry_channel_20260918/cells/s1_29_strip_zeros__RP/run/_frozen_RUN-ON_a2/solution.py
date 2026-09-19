def strip_zeros(s: str) -> str:
    if "." not in s:
        return s
    
    parts = s.split(".")
    integer_part = parts[0]
    fractional_part = parts[1]
    
    # Remove trailing zeros from fractional part
    fractional_part = fractional_part.rstrip("0")
    
    if not fractional_part:
        return integer_part
    else:
        return f"{integer_part}.{fractional_part}"

def tidy_decimal(s: str) -> str:
    if "." not in s:
        return s
    
    parts = s.split(".")
    integer_part = parts[0]
    fractional_part = parts[1] if len(parts) > 1 else ""
    
    # Remove trailing zeros from fractional part
    fractional_part = fractional_part.rstrip("0")
    
    if not fractional_part:
        return integer_part
    else:
        return f"{integer_part}.{fractional_part}"

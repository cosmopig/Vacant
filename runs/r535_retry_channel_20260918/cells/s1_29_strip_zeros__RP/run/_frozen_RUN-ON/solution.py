def tidy_decimal(s: str) -> str:
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

# Examples and testing (optional but good for verification)
if __name__ == "__main__":
    assert tidy_decimal("1.234") == "1.234"
    assert tidy_decimal("1.230") == "1.23"
    assert tidy_decimal("1.2300") == "1.23"
    assert tidy_decimal("1.") == "1"
    assert tidy_decimal("1.0") == "1"
    assert tidy_decimal("1.000") == "1"
    assert tidy_decimal("1.23456789") == "1.23456789"
    assert tidy_decimal("10.00") == "10"
    assert tidy_decimal("0.123") == "0.123"
    assert tidy_decimal("0.120") == "0.12"
    assert tidy_decimal("5") == "5"
    assert tidy_decimal("0") == "0"

def strip_zeros(s: str) -> str:
    if "." not in s:
        return s
    
    parts = s.split(".")
    integer_part = parts[0]
    fractional_part = parts[1]
    
    # Remove trailing zeros from the fractional part
    stripped_fractional = fractional_part.rstrip("0")
    
    if stripped_fractional == "":
        return integer_part
    else:
        return f"{integer_part}.{stripped_fractional}"

# Examples for testing (optional, but good to verify)
if __name__ == "__main__":
    assert strip_zeros("1.230") == "1.23"
    assert strip_zeros("1.000") == "1"
    assert strip_zeros("1.2345") == "1.2345"
    assert strip_zeros("100") == "100"
    assert strip_zeros("0.000") == "0"
    assert strip_zeros(".500") == ".5"

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

# Examples to test (optional, but good for verification)
if __name__ == "__main__":
    print(tidy_decimal("1.234"))      # 1.234
    print(tidy_decimal("1.230"))      # 1.23
    print(tidy_decimal("1.2300"))     # 1.23
    print(tidy_decimal("1."))         # 1
    print(tidy_decimal("1.000"))      # 1
    print(tidy_decimal("1,234"))      # 1,234 (no dot)
    print(tidy_decimal("0.500"))       # 0.5
    print(tidy_decimal(".500"))        # .5

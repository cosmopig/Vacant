def tidy_decimal(s: str) -> str:
    if "." not in s:
        return s
    
    parts = s.split(".")
    integer_part = parts[0]
    fractional_part = parts[1]
    
    # Remove trailing zeros from fractional part
    trimmed_fractional = fractional_part.rstrip("0")
    
    if trimmed_fractional == "":
        return integer_part
    else:
        return f"{integer_part}.{trimmed_fractional}"

if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        print(tidy_decimal(line.strip()))

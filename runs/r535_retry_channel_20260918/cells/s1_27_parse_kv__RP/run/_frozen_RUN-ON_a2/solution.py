def parse_kv(line: str) -> dict[str, str]:
    """
    Parses a settings line made of name-and-value pairs.

    Args:
        line: A string containing name=value pairs separated by semicolons.

    Returns:
        A dictionary mapping names to values.
    """
    settings = {}
    # Split the line into individual pairs by semicolon
    pairs = line.split(';')
    
    for pair in pairs:
        if not pair.strip():
            continue
            
        # Each pair should contain an equals sign
        if '=' in pair:
            name, value = pair.split('=', 1)
            # Strip whitespace from both name and value
            settings[name.strip()] = value.strip()
            
    return settings

# Example usage (optional, for testing):
if __name__ == "__main__":
    test_line = "host=localhost; port=8080; timeout=30 ; host=127.0.0.1;  "
    print(parse_kv(test_line))

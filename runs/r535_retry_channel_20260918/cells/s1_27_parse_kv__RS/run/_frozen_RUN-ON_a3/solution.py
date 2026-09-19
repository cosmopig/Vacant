def parse_settings(line: str) -> dict[str, str]:
    """
    Parses a settings line made of name-and-value pairs.

    Pairs are separated by semicolons. Inside a pair the name comes before an
    equals sign and the value after it. Spaces around a name or a value are not
    part of it. A stretch between two semicolons with nothing in it is skipped.

    Build the lookup from name to value, both kept as text. When the same name
    appears more than once, the later one wins.
    """
    settings = {}
    # Split by semicolon to get individual pairs
    pairs = line.split(';')
    for pair in pairs:
        if not pair.strip():
            continue
        
        # Each pair should have an equals sign
        if '=' in pair:
            name, value = pair.split('=', 1)
            # Strip whitespace from name and value
            settings[name.strip()] = value.strip()
            
    return settings

if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("host=localhost;port=8080", {"host": "localhost", "port": "8080"}),
        ("host=localhost; port= 8080 ; timeout=30 ", {"host": "localhost", "port": "8080", "timeout": "30"}),
        ("name=user1; name=user2", {"name": "user2"}),
        (";;;", {}),
        ("key1=val1;;key2=val2", {"key1": "val1", "key2": "val2"}),
        ("  space_before = value ; space_after = value  ", {"space_before": "value", "space_after": "value"}),
    ]

    for line, expected in test_cases:
        result = parse_settings(line)
        assert result == expected, f"Failed for '{line}': expected {expected}, got {result}"
    print("All tests passed!")

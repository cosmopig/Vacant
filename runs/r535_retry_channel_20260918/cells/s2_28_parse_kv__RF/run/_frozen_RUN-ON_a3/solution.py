def parse_kv(line):
    result = {}
    # Split by semicolon to get individual pairs
    pairs = line.split(';')
    for pair in pairs:
        if not pair.strip():
            continue
        
        # Split by equals sign to separate name and value
        if '=' in pair:
            name, value = pair.split('=', 1)
            # Strip whitespace from both name and value
            name = name.strip()
            value = value.strip()
            # If name is not empty, add it to the dictionary
            # Note: The task says "both the same name written twice" turn up in real files.
            # Usually, the last one wins in a dictionary update.
            if name:
                result[name] = value
    return result

if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("name=value;age=25", {"name": "value", "age": "25"}),
        ("name=value;;age=25", {"name": "value", "age": "25"}),
        (" name = value ; age = 25 ", {"name": "value", "age": "25"}),
        ("name=value;name=new_value", {"name": "new_value"}),
        ("invalid_pair;name=value", {"name": "value"}),
        ("=value", {}),
    ]

    for line, expected in test_cases:
        actual = parse_kv(line)
        assert actual == expected, f"Failed on {line}: expected {expected}, got {actual}"
    print("All tests passed!")

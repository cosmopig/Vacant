def parse_kv(line):
    result = {}
    # Split by semicolon to get individual pairs
    pairs = line.split(';')
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        
        # Check if the pair contains an equals sign
        if '=' not in pair:
            continue
            
        # Split by the first equals sign found
        name, value = pair.split('=', 1)
        name = name.strip()
        value = value.strip()
        
        # If name is empty (e.g., "=value"), we might want to skip it or handle it.
        # The task says "lookup from name to value", usually implies non-empty names.
        if name:
            result[name] = value
            
    return result

# Example usage and testing:
if __name__ == "__main__":
    test_cases = [
        ("name=value;age=25", {"name": "value", "age": "25"}),
        ("name=value;;age=25", {"name": "value", "age": "25"}),
        ("  name  =  value  ; age = 25 ", {"name": "value", "age": "25"}),
        ("name=value;name=new_value", {"name": "new_value"}), # Same name written twice (last one wins)
        ("name=value;invalid_pair;age=25", {"name": "value", "age": "25"}), # Missing equals sign
        ("=value;name=value", {"name": "value"}), # Pair with missing name
    ]

    for line, expected in test_cases:
        actual = parse_kv(line)
        assert actual == expected, f"Failed for '{line}': expected {expected}, got {actual}"
    print("All tests passed!")

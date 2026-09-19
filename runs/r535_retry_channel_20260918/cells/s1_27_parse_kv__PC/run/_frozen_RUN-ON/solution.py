def parse_kv(line: str) -> dict[str, str]:
    result = {}
    # Split by semicolon to get pairs
    pairs = line.split(';')
    for pair in pairs:
        if not pair.strip():
            continue
        
        # Split by equals sign into name and value
        if '=' in pair:
            name_part, value_part = pair.split('=', 1)
            # Strip whitespace from both name and value
            name = name_part.strip()
            value = value_part.strip()
            
            if name:
                result[name] = value
    return result

if __name__ == "__main__":
    # Test cases
    assert parse_kv("name=John; age=30") == {"name": "John", "age": "30"}
    assert parse_kv("name=John;  age= 30 ; color=blue ") == {"name": "John", "age": "30", "color": "blue"}
    assert parse_kv("name=John;;age=30") == {"name": "John", "age": "30"}
    assert parse_kv("name=John; name=Doe") == {"name": "Doe"}
    assert parse_kv("  name = John ; age = 30  ") == {"name": "John", "age": "30"}
    assert parse_kv("") == {}
    assert parse_kv(";") == {}
    print("All tests passed!")

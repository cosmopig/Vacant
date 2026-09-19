def parse_kv(line):
    pairs = line.split(';')
    result = {}
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        if '=' not in pair:
            raise ValueError("Pair with no equals sign")
        name, value = pair.split('=', 1)
        result[name.strip()] = value.strip()
    return result

# Test cases
if __name__ == "__main__":
    assert parse_kv("name=value;age=25") == {"name": "value", "age": "25"}
    assert parse_kv("name=value;;age=25") == {"name": "value", "age": "25"}
    assert parse_kv("name=value;name=new_value") == {"name": "new_value"}
    assert parse_kv("  name = value ; age = 30 ") == {"name": "value", "age": "30"}
    
    try:
        parse_kv("name=value;invalid_pair")
    except ValueError:
        pass # Expected
    else:
        raise AssertionError("Should have raised ValueError for missing equals sign")

    print("All tests passed!")

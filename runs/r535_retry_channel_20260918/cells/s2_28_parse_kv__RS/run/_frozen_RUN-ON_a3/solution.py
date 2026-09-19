def parse_kv(line):
    result = {}
    # Split by semicolon to get individual pairs
    pairs = line.split(';')
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        
        # Check if it contains an equals sign
        if '=' in pair:
            name, value = pair.split('=', 1)
            name = name.strip()
            value = value.strip()
            # If the same name is written twice, the last one wins (standard dict behavior)
            # or we could choose to keep the first. The prompt says "both the same name 
            # written twice ... turn up", usually implying standard dictionary update logic.
            if name:
                result[name] = value
        else:
            # A pair with its equals sign missing - the prompt doesn't specify what to do,
            # but typically we skip it or handle it as a key with no value. 
            # Given "gives back the lookup from name to value", if there is no '=', 
            # there is no value. We will skip it based on common parsing logic.
            pass
    return result

if __name__ == "__main__":
    # Test cases
    test_lines = [
        "name=value;age=25",
        "  name=value ; age=25 ",
        "name=value;;age=25",
        "name=value;name=new_value",
        "invalid_pair;name=value",
    ]
    
    for line in test_lines:
        print(f"Line: {line!r} -> {parse_kv(line)}")

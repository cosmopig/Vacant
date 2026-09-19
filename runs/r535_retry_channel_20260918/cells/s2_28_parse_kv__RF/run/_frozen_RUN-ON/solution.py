def parse_kv(line):
    result = {}
    # Split by semicolon to get pairs
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
            # or we could choose to keep the first. The prompt says "gives back the lookup",
            # usually implying a dictionary where later entries overwrite earlier ones if not specified.
            if name:
                result[name] = value
        else:
            # A pair with its equals sign missing - the prompt doesn't specify what to do 
            # other than saying they "turn up". Usually, we ignore them or handle as needed.
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
        "   ;   ",
    ]
    
    for line in test_lines:
        print(f"Line: '{line}' -> {parse_kv(line)}")

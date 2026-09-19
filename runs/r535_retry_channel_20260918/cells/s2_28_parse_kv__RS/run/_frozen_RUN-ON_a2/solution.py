def parse_kv(line):
    result = {}
    # Split by semicolon to get individual pairs
    pairs = line.split(';')
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        
        # Check if '=' is present
        if '=' in pair:
            name, value = pair.split('=', 1)
            name = name.strip()
            value = value.strip()
            # If name exists, it's overwritten (or we could handle duplicates differently, 
            # but standard behavior for "lookup from name to value" usually implies last one wins)
            if name:
                result[name] = value
        else:
            # A pair with its equals sign missing - the task says these turn up.
            # Usually, we just ignore them or handle as needed. 
            # The prompt doesn't specify what to do with them other than they "turn up".
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

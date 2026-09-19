def parse_kv(line):
    result = {}
    # Split by semicolon to get individual pairs
    pairs = line.split(';')
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        
        # Check if the pair contains an equals sign
        if '=' in pair:
            name, value = pair.split('=', 1)
            name = name.strip()
            value = value.strip()
            # If name is empty (e.g., "=value"), we can choose to skip or keep it.
            # The task says "both the same name written twice", implying we should overwrite.
            if name:
                result[name] = value
        else:
            # A pair with its equals sign missing - the task doesn't specify what to do,
            # but usually these are ignored or handled as keys with empty values.
            # Given "both the same name written twice", it implies we only care about valid pairs.
            pass
    return result

if __name__ == "__main__":
    # Test cases
    print(parse_kv("name=value;age=25"))  # {'name': 'value', 'age': '25'}
    print(parse_kv("name=value;;age=25")) # {'name': 'value', 'age': '25'}
    print(parse_kv("name=value; name=new_value")) # {'name': 'new_value'}
    print(parse_kv("invalid_pair;name=value")) # {'name': 'value'}

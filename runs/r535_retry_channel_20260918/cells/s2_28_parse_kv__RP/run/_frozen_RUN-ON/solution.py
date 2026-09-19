def parse_kv(line):
    result = {}
    # Split by semicolon to get individual pairs
    pairs = line.split(';')
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        
        # Check if '=' is present and not at the start/end (though requirements say "missing" means skip or handle)
        if '=' in pair:
            name, value = pair.split('=', 1)
            name = name.strip()
            value = value.strip()
            # If name is empty but there was an equals sign, it's technically a pair with missing name
            # The prompt says "pair with its equals sign missing turn up", implying we should ignore them or handle them.
            # Usually, if name is empty, we skip it unless specified otherwise.
            if name:
                result[name] = value
        else:
            # Pair with its equals sign missing - the prompt says these "turn up" but doesn't explicitly say to ignore.
            # However, since it's a KV parser, if there's no '=', we can't really parse it as a pair.
            pass
    return result

# Example usage (not required by task but good for verification):
# print(parse_kv("name=John; age=30;  ")) -> {'name': 'John', 'age': '30'}
# print(parse_kv("name=John; name=Doe")) -> {'name': 'Doe'} (last one wins)
# print(parse_kv("name=John; age30"))    -> {'name': 'John'}

def parse_kv(line):
    result = {}
    pairs = line.split(';')
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        
        if '=' not in pair:
            raise ValueError("Missing equals sign")
            
        name, value = pair.split('=', 1)
        name = name.strip()
        value = value.strip()
        
        if name:
            result[name] = value
    return result

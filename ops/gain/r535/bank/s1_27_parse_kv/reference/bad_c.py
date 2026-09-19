def parse_settings(line):
    out = {}
    for part in line.split(";"):
        if not part.strip():
            continue
        name, _, value = part.partition("=")
        out[name.strip()] = value.strip()
    return out

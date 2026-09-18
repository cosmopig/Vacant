def parse_kv(line):
    out = {}
    for part in line.split(";"):
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        out[name.strip()] = value.strip()
    return out

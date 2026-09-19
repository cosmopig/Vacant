def parse_settings(line):
    out = {}
    for part in line.split(";"):
        if not part.strip():
            continue
        if "=" not in part:
            raise ValueError("no '=' in %r" % part)
        name, _, value = part.partition("=")
        out[name.strip()] = value.strip()
    return out

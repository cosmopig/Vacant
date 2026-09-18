def camelise(s):
    parts = s.split("_")
    return parts[0].lower() + "".join(
        p[:1].upper() + p[1:].lower() for p in parts[1:])

def camelise(s):
    parts = s.split("_")
    return "".join(p[:1].upper() + p[1:].lower() for p in parts)

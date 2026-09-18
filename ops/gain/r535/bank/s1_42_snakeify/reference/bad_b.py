def snakeify(s):
    out = []
    for i, c in enumerate(s):
        if c.isupper() and i > 0:
            out.append("_")
        out.append(c.upper())
    return "".join(out)

def snakeify(s):
    out = []
    for c in s:
        if c.isupper():
            out.append("_")
        out.append(c.lower())
    return "".join(out)

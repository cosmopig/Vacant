def squeeze(s):
    out = []
    prev_space = False
    for c in s:
        if c.isspace():
            if not prev_space:
                out.append(" ")
            prev_space = True
        else:
            out.append(c)
            prev_space = False
    return "".join(out)

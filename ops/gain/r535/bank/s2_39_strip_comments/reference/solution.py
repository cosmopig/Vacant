def strip_comments(text):
    out = []
    for line in text.split("\n"):
        out.append(line.split("#", 1)[0].rstrip())
    return "\n".join(out)

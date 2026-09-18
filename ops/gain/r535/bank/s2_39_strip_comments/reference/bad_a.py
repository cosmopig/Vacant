def strip_comments(text):
    out = []
    for line in text.split("\n"):
        head = line.split("#", 1)[0].rstrip()
        if head:
            out.append(head)
    return "\n".join(out)

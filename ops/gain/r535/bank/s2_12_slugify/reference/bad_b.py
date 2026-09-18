def slugify(s):
    t = "".join(c if c.isalnum() else "-" for c in s.lower())
    while "--" in t:
        t = t.replace("--", "-")
    return t

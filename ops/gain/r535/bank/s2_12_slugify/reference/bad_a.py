def slugify(s):
    t = "".join(c if c.isalnum() else "-" for c in s.lower())
    return t.strip("-")

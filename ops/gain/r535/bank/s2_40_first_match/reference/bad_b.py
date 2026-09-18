def first_match(words, prefix):
    p = prefix.lower()
    for w in words:
        if w.lower().startswith(p):
            return w
    raise ValueError("no match")

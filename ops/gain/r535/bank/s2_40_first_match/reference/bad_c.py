def find_first(words, prefix):
    p = prefix.lower()
    for w in words:
        if w.lower().startswith(p):
            return w
    return None

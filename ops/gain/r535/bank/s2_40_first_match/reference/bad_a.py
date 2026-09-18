def first_match(words, prefix):
    for w in words:
        if w.startswith(prefix):
            return w
    return None

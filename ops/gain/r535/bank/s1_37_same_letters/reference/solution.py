def _key(t):
    return sorted(t.lower().replace(" ", ""))


def same_letters(a, b):
    return _key(a) == _key(b)

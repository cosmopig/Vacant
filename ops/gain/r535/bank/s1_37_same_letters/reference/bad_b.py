def same_letters(a, b):
    return set(a.lower().replace(" ", "")) == set(b.lower().replace(" ", ""))

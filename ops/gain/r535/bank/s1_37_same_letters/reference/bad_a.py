def same_letters(a, b):
    return sorted(a.replace(" ", "")) == sorted(b.replace(" ", ""))

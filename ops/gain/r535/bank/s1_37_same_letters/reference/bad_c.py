def is_anagram(a, b):
    def key(t):
        return sorted(t.lower().replace(" ", ""))
    return key(a) == key(b)

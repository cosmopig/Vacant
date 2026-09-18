def pluralize(word, n):
    if n == 1:
        return word
    if word.endswith(("s", "x", "ch", "sh")):
        return word + "es"
    return word + "s"

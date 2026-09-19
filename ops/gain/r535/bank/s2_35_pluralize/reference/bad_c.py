def plural(word, n):
    if n == 1:
        return "1 %s" % word
    if word.endswith(("s", "x", "ch", "sh")):
        return "%d %ses" % (n, word)
    return "%d %ss" % (n, word)

def pluralize(word, n):
    if n == 1:
        return "1 %s" % word
    return "%d %ss" % (n, word)

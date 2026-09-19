def first_match(words, prefix):
    for word in words:
        if word.startswith(prefix):
            return word
    return None

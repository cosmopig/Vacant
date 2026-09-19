def first_match(words, prefix):
    for word in words:
        if word.lower().startswith(prefix.lower()):
            return word
    return None

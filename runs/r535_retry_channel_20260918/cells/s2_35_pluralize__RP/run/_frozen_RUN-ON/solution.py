def pluralize(word, n):
    if n == 1:
        return f"1 {word}"

    if word.endswith(('s', 'ch', 'sh', 'x')):
        return f"{n} {word}es"
    elif word.endswith('y'):
        if len(word) > 1 and word[-2].isalpha() and word[-2] != 'i':
            return f"{n} {word[:-1]}ies"
        else:
            return f"{n} {word}s"
    elif word.endswith('o'):
        # Common for words like "potato", "hero"
        return f"{n} {word}es"
    else:
        return f"{n} {word}s"

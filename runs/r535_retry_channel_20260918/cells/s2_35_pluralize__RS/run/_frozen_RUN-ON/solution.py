def pluralize(word, n):
    if n == 1:
        return f"1 {word}"
    
    # Handle common cases that need 'es' (extra syllable)
    if word.endswith(('s', 'x', 'ch', 'sh')):
        return f"{n} {word}es"
    # Handle words ending in 'y'
    elif word.endswith('y'):
        if len(word) > 1 and word[-2] in "aeiou":
            return f"{n} {word[:-1]}ies"
        else:
            return f"{n} {word}s"
    # Default case for most other words
    else:
        return f"{n} {word}s"

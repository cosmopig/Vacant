def pluralize(word, n):
    if n == 1:
        return f"1 {word}"
    
    # Handle words ending in s, x, ch, sh (add -es)
    if word.endswith(('s', 'x', 'ch', 'sh')):
        return f"{n} {word}es"
    # Handle words ending in y preceded by a consonant (replace y with -ies)
    elif word.endswith('y') and len(word) > 1 and word[-2] not in 'aeiou':
        return f"{n} {word[:-1]}ies"
    # Default case: add -s
    else:
        return f"{n} {word}s"

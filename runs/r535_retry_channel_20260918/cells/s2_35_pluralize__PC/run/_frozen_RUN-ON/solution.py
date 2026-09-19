def pluralize(word, n):
    if n == 1:
        return f"1 {word}"
    
    # A word ending in s, x, ch or sh takes es rather than s.
    if word.endswith(('s', 'x', 'ch', 'sh')):
        plural_word = word + "es"
    else:
        plural_word = word + "s"
        
    return f"{n} {plural_word}"

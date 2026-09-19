def group_by_first(words):
    groups = {}
    for word in words:
        if not word:
            continue
        first_char = word[0].lower()
        if first_char not in groups:
            groups[first_char] = []
        groups[first_char].append(word)
    return groups

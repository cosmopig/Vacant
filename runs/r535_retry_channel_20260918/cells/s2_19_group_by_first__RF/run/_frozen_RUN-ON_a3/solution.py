def group_by_first(words):
    groups = {}
    for word in words:
        if not word:
            continue
        first_letter = word[0]
        if first_letter not in groups:
            groups[first_letter] = []
        groups[first_letter].append(word)
    return groups

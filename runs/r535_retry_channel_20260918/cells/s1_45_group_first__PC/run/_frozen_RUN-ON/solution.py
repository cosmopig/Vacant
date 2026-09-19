def group_first(words):
    groups = {}
    for word in words:
        first_letter = word[0].lower()
        if first_letter not in groups:
            groups[first_letter] = []
        groups[first_letter].append(word)
    return groups

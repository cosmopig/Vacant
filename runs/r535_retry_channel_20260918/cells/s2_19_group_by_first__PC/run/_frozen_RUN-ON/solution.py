from collections import defaultdict

def group_by_first(words):
    groups = defaultdict(list)
    for word in words:
        if not word:
            continue
        first_letter = word[0].lower()
        groups[first_letter].append(word)
    return dict(groups)

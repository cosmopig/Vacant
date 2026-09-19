from collections import defaultdict

def sort_words(words):
    groups = defaultdict(list)
    for word in words:
        first_letter = word[0].lower()
        groups[first_letter].append(word)
    return dict(groups)

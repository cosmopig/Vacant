from collections import defaultdict

def group_by_first(words):
    groups = defaultdict(list)
    for word in words:
        if word:
            groups[word[0]].append(word)
    return dict(groups)

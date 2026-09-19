from collections import defaultdict

def sort_words(words):
    groups = defaultdict(list)
    for word in words:
        if word:
            first_letter = word[0].lower()
            groups[first_letter].append(word)
    return dict(groups)

# Example usage (optional, but good for testing if needed):
# words = ["Apple", "banana", "Apricot", "cherry"]
# print(sort_words(words))

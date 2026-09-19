from collections import defaultdict

def sort_words(words):
    groups = defaultdict(list)
    for word in words:
        first_letter = word[0].lower()
        groups[first_letter].append(word)
    return dict(groups)

if __name__ == "__main__":
    import sys
    input_words = sys.stdin.read().split()
    result = sort_words(input_words)
    print(result)

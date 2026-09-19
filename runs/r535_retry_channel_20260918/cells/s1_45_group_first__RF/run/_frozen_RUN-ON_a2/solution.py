from collections import defaultdict

def sort_words(words):
    groups = defaultdict(list)
    for word in words:
        first_letter = word[0].lower()
        groups[first_letter].append(word)
    return dict(groups)

if __name__ == "__main__":
    import sys
    # Example usage if needed, but the task just says write the code.
    # Let's assume a standard way to call it or just provide the function.
    pass

def sort_words(words):
    return sorted(words, key=len)

if __name__ == "__main__":
    import sys
    # Read all words from stdin, split by whitespace
    words = sys.stdin.read().split()
    print(*(sort_words(words)))

def sort_words(words):
    return sorted(words, key=len)

if __name__ == "__main__":
    import sys
    input_data = sys.stdin.read().splitlines()
    for word in sort_words(input_data):
        print(word)

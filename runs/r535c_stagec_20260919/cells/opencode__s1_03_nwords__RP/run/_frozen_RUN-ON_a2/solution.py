def n_words(text):
    return len(text.split())

if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        print(n_words(line))

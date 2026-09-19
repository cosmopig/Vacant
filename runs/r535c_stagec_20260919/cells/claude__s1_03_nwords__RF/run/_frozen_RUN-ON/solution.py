def count_words(text):
    return len(text.split())

if __name__ == "__main__":
    import sys
    line = sys.stdin.read().strip()
    print(count_words(line))

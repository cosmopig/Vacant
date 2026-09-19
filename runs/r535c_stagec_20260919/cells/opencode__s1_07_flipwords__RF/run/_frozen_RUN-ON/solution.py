def flip_words(sentence: str) -> str:
    words = sentence.split()
    return " ".join(reversed(words))

if __name__ == "__main__":
    import sys
    input_text = sys.stdin.read().strip()
    print(flip_words(input_text))

def reverse_sentence(sentence: str) -> str:
    words = sentence.split()
    return " ".join(reversed(words))

if __name__ == "__main__":
    import sys
    input_sentence = sys.stdin.read().strip()
    print(reverse_sentence(input_sentence))

import sys

def reverse_sentence(sentence: str) -> str:
    words = sentence.split()
    return " ".join(reversed(words))

if __name__ == "__main__":
    input_data = sys.stdin.read().strip()
    if input_data:
        print(reverse_sentence(input_data))

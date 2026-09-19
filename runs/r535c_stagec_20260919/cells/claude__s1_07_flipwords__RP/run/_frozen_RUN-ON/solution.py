import sys

def reverse_sentence():
    # Read input from stdin
    input_data = sys.stdin.read()
    if not input_data:
        return

    # Split by whitespace (handles multiple spaces, tabs, newlines)
    words = input_data.split()

    # Reverse the list of words
    reversed_words = words[::-1]

    # Join with a single space and print
    print(" ".join(reversed_words))

if __name__ == "__main__":
    reverse_sentence()

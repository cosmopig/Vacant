import re

def count_words(text):
    # Use regex to find all sequences of non-whitespace characters.
    # This naturally handles multiple whitespaces and leading/trailing whitespace.
    words = re.findall(r'\S+', text)
    return len(words)

if __name__ == "__main__":
    import sys
    # Read from stdin or a single line argument if provided,
    # but the task implies processing "a line of text".
    # Let's assume we read one line from standard input.
    line = sys.stdin.readline()
    if line:
        print(count_words(line))

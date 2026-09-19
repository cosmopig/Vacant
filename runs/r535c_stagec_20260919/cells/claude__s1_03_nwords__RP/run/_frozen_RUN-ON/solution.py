import sys

def count_words(text):
    # .split() without arguments splits by any whitespace and removes empty strings,
    # which correctly handles leading/trailing whitespace and multiple spaces between words.
    return len(text.split())

if __name__ == "__main__":
    # Read the entire input from stdin (or just one line if that's what's expected)
    # The task says "a line of text", so we read one line.
    line = sys.stdin.readline()
    if line:
        print(count_words(line))

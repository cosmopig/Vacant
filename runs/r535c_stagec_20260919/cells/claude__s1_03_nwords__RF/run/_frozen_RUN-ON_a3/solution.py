import sys

def count_words(text):
    # split() without arguments splits by any whitespace and discards empty strings
    return len(text.split())

if __name__ == "__main__":
    # Read from stdin to handle multi-line input or single line as needed
    # The task says "a line of text", so we'll read one line.
    line = sys.stdin.readline()
    if line:
        print(count_words(line))

import sys

def count_words(text):
    # split() without arguments splits by any whitespace and discards empty strings
    return len(text.split())

if __name__ == "__main__":
    # Read from stdin line by line
    for line in sys.stdin:
        print(count_words(line))

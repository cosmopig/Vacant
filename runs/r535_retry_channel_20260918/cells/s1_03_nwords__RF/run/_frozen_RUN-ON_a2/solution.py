import sys

def count_words(line):
    # split() without arguments splits by any whitespace and discards empty strings
    return len(line.split())

if __name__ == "__main__":
    for line in sys.stdin:
        print(count_words(line))

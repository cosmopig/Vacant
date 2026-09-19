import sys

def solve():
    for line in sys.stdin:
        # Remove the trailing newline character only
        line_content = line.rstrip('\r\n')
        # Split by comma and strip whitespace from each field
        fields = [f.strip() for f in line_content.split(',')]
        # Print the fields joined by a space
        print(" ".join(fields))

if __name__ == "__main__":
    solve()

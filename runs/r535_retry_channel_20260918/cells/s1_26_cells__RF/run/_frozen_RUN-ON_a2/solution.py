import sys

def solve():
    for line in sys.stdin:
        # Remove trailing newline characters
        line = line.rstrip('\r\n')
        
        # If the line is completely empty, it has one field which is an empty string.
        if not line:
            print("['']")
            continue
            
        # Split by comma and strip whitespace from each field
        fields = [f.strip() for f in line.split(',')]
        # Print the list of fields as a string representation
        print(str(fields))

if __name__ == "__main__":
    solve()

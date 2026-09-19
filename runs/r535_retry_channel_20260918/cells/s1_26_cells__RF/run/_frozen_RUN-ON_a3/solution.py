import sys

def solve():
    for line in sys.stdin:
        # Remove trailing newline characters
        line = line.rstrip('\r\n')
        
        # A line with nothing in it has one field, and that field is text with nothing in it.
        if not line:
            print("")
            continue
            
        # Split by comma and strip whitespace from each field
        fields = [f.strip() for f in line.split(',')]
        
        # The task says "give back its fields". 
        # Since no specific format is given, I'll print them joined by a space.
        print(" ".join(fields))

if __name__ == "__main__":
    solve()

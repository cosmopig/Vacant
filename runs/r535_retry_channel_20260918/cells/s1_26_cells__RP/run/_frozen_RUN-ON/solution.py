import sys

def solve():
    line = sys.stdin.readline()
    if not line:
        return
    
    # Remove trailing newline
    line = line.rstrip('\r\n')
    
    # Split by comma
    fields = line.split(',')
    
    # Strip spaces from each field and print them one per line
    for field in fields:
        print(field.strip())

if __name__ == "__main__":
    solve()

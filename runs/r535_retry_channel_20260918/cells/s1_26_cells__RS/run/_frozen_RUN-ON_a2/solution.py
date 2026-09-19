import sys

def solve():
    for line in sys.stdin:
        line = line.rstrip('\r\n')
        if not line:
            print("")
            continue
        fields = [f.strip() for f in line.split(',')]
        print('\n'.join(fields))

if __name__ == "__main__":
    solve()

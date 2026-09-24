import sys

def solve():
    line = sys.stdin.readline()
    if not line:
        return
    parts = line.split()
    if len(parts) < 2:
        return
    
    try:
        q1 = float(parts[0])
        q2 = float(parts[1])

        if q2 == 0:
            pass
        else:
            percentage = (q1 / q2) * 100
            print(f"{percentage:.1f}")
    except ValueError:
        pass

if __name__ == "__main__":
    solve()

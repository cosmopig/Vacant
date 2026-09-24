import sys

def solve():
    line = sys.stdin.readline()
    if not line:
        return
    parts = line.split()
    if len(parts) < 2:
        return
    year = int(parts[0])
    month = int(parts[1])

    if month in [4, 6, 9, 11]:
        print(30)
    elif month == 2:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            print(29)
        else:
            print(28)
    else:
        print(31)

if __name__ == "__main__":
    solve()

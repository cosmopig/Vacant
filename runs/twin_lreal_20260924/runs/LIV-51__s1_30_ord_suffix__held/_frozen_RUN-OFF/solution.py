import sys

def solve():
    line = sys.stdin.readline()
    if not line:
        return
    try:
        n_str = line.strip()
        if not n_str:
            return
        n = int(n_str)
    except ValueError:
        return

    # The prompt says "Write a positive whole number the way it is said when counting positions"
    # and "the number itself followed by the two-letter ending that goes with it".
    # This means for 1, it's "1st", for 2, it's "2nd", etc.
    # The exceptions are 11, 12, 13 which take the plain ending (th).

    if n % 100 in [11, 12, 13]:
        print(f"{n}th")
    else:
        last_digit = n % 10
        if last_digit == 1:
            print(f"{n}st")
        elif last_digit == 2:
            print(f"{n}nd")
        elif last_digit == 3:
            print(f"{n}rd")
        else:
            print(f"{n}th")

if __name__ == "__main__":
    solve()

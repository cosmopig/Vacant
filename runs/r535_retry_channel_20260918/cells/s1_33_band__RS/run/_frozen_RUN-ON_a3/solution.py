import sys

def solve():
    # The task doesn't specify an input, but usually these problems 
    # expect to read from stdin.
    input_data = sys.stdin.read().strip()
    if not input_data:
        return
    try:
        mark = int(input_data)
    except ValueError:
        return

    if mark >= 90:
        print("A")
    elif mark >= 80:
        print("B")
    elif mark >= 70:
        print("C")
    elif mark >= 60:
        print("D")
    else:
        # "anything lower is the fifth letter used -- which is not the fifth letter of the alphabet."
        # The 5th letter of the alphabet is 'E'.
        # In US schools, the grades are A, B, C, D, F.
        print("F")

if __name__ == "__main__":
    solve()

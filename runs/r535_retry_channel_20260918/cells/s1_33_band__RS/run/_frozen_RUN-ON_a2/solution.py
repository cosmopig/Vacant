import sys

def solve():
    # Read input from stdin
    line = sys.stdin.readline().strip()
    if not line:
        return
    try:
        score = int(line)
    except ValueError:
        return

    # Grading logic:
    # 90+ : A
    # 80-89: B
    # 70-79: C
    # 60-69: D
    # <60  : F (The fifth letter used is not the fifth letter of the alphabet, which is E. So it's F.)

    if score >= 90:
        print("A")
    elif score >= 80:
        print("B")
    elif score >= 70:
        print("C")
    elif score >= 60:
        print("D")
    else:
        print("F")

if __name__ == "__main__":
    solve()

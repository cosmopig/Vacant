import sys

def solve():
    input_data = sys.stdin.read().split()
    if len(input_data) < 2:
        return

    try:
        q1 = float(input_data[0])
        q2 = float(input_data[1])
    except ValueError:
        return

    if q2 == 0:
        print()
    else:
        percentage = (q1 / q2) * 100
        # Use format to ensure one decimal place and handle rounding correctly
        print(f"{percentage:.1f}")

if __name__ == "__main__":
    solve()

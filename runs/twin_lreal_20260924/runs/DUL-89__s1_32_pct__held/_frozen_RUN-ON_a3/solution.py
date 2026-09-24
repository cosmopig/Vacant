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
        print("nothing at all")
    else:
        percentage = (q1 / q2) * 100
        # The prompt says "rounded to one decimal place".
        # f"{val:.1f}" rounds correctly for display.
        print(f"{round(percentage, 1):.1f}")

if __name__ == "__main__":
    solve()

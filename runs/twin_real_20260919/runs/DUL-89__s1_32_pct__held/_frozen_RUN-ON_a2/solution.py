import sys

def solve():
    input_data = sys.stdin.read().split()
    if len(input_data) < 2:
        return
    
    try:
        quantity1 = float(input_data[0])
        quantity2 = float(input_data[1])

        if quantity2 == 0:
            print("")
        else:
            percentage = (quantity1 / quantity2) * 100
            # Using format to ensure one decimal place even if it's .0
            print(f"{round(percentage, 1):.1f}")
    except ValueError:
        pass

if __name__ == "__main__":
    solve()

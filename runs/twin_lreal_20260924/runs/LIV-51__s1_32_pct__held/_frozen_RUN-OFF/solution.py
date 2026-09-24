import sys

def main():
    input_data = sys.stdin.read().split()
    if len(input_data) < 2:
        return

    try:
        q1 = float(input_data[0])
        q2 = float(input_data[1])
        
        if q2 == 0:
            # "the answer is nothing at all rather than an error"
            pass
        else:
            percentage = (q1 / q2) * 100
            print(f"{round(percentage, 1):.1f}")
    except ValueError:
        pass

if __name__ == "__main__":
    main()

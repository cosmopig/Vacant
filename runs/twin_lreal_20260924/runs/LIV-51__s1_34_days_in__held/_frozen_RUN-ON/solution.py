import sys

def solve():
    # The problem says "The year is the first argument and the month is the second"
    # This usually refers to command line arguments in these types of tasks.
    if len(sys.argv) < 3:
        return
    try:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        
        if month == 2:
            if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                print(29)
            else:
                print(28)
        elif month in [4, 6, 9, 11]:
            print(30)
        else:
            print(31)
    except ValueError:
        pass

if __name__ == "__main__":
    solve()

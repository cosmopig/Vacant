import sys

def solve():
    # The problem says "The year is the first argument and the month is the second"
    # This usually refers to command line arguments in these types of tasks.
    if len(sys.argv) < 3:
        return

    try:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
    except ValueError:
        return

    # Days in each month (non-leap year)
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    # Check for leap year
    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    
    if month == 2 and is_leap:
        print(29)
    else:
        # Month is 1-indexed, so we use month - 1
        print(days_in_month[month - 1])

if __name__ == "__main__":
    solve()

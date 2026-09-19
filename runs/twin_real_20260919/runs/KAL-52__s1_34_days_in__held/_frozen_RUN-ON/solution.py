import datetime
import sys

def solve():
    # The problem says "The year is the first argument and the month is the second"
    # This usually means command-line arguments in these types of tasks.
    if len(sys.argv) == 3:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
    else:
        # Fallback to stdin if no arguments are provided
        input_data = sys.stdin.read().split()
        if len(input_data) < 2:
            return
        year = int(input_data[0])
        month = int(input_data[1])

    # Use datetime to find the last day of the month
    if month == 12:
        next_month = datetime.date(year + 1, 1, 1)
    else:
        next_month = datetime.date(year, month + 1, 1)
        
    # The day before the first day of next month is the last day of current month
    last_day = (next_month - datetime.timedelta(days=1)).day
    print(last_day)

if __name__ == "__main__":
    solve()

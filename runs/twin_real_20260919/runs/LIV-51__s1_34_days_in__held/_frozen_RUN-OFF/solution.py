import datetime
import sys

def solve():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    year = int(input_data[0])
    month = int(input_data[1])
    
    # Use datetime to find the last day of the month
    # If it's December, the next month is January of the next year
    if month == 12:
        next_month = datetime.date(year + 1, 1, 1)
    else:
        next_month = datetime.date(year, month + 1, 1)
        
    # The day before the first day of next month is the last day of current month
    last_day = (next_month - datetime.timedelta(days=1)).day
    print(last_day)

if __name__ == "__main__":
    solve()

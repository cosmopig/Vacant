import sys
from datetime import date, timedelta

def solve():
    input_data = sys.stdin.read().split()
    if len(input_data) < 2:
        return
    
    try:
        year = int(input_data[0])
        month = int(input_data[1])
        
        # The last day of the month is the day before the first day of the next month.
        if month == 12:
            next_month_date = date(year + 1, 1, 1)
        else:
            next_month_date = date(year, month + 1, 1)
        
        last_day = (next_month_date - timedelta(days=1)).day
        print(last_day)
    except ValueError:
        pass

if __name__ == "__main__":
    solve()

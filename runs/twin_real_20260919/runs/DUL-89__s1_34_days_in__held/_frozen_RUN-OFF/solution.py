import sys
from datetime import date, timedelta

def solve():
    line = sys.stdin.readline()
    if not line:
        return
    parts = line.split()
    if len(parts) < 2:
        return
    
    year = int(parts[0])
    month = int(parts[1])

    # Determine the first day of the next month
    if month == 12:
        next_month_date = date(year + 1, 1, 1)
    else:
        next_month_date = date(year, month + 1, 1)

    # The last day is one day before the first of next month
    last_day_date = next_month_date - timedelta(days=1)
    print(last_day_date.day)

if __name__ == "__main__":
    solve()

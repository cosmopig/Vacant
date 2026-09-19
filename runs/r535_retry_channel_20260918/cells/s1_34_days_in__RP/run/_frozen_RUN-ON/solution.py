import datetime

def solve():
    try:
        line = input().split()
        if not line:
            return
        year = int(line[0])
        month = int(line[1])
        
        # Use datetime to find the number of days in a month
        # We can get the first day of the next month and subtract one day
        if month == 12:
            next_month = datetime.date(year + 1, 1, 1)
        else:
            next_month = datetime.date(year, month + 1, 1)
            
        first_day_of_current_month = datetime.date(year, month, 1)
        # The number of days is the difference between first day of next month and first day of current month
        print((next_month - first_day_of_current_month).days)
    except EOFError:
        pass

if __name__ == "__main__":
    solve()

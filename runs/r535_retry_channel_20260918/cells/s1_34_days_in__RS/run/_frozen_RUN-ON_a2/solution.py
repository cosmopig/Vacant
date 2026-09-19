import datetime

def solve():
    try:
        line = input().split()
        if not line:
            return
        year = int(line[0])
        month = int(line[1])
        
        # Use a dummy day (1) to find the last day of the month
        if month == 12:
            next_month = datetime.date(year + 1, 1, 1)
        else:
            next_month = datetime.date(year, month + 1, 1)
            
        first_day_of_current_month = datetime.date(year, month, 1)
        # The number of days is the difference between the first day of next month and first day of current month
        print((next_month - first_day_of_current_month).days)
    except EOFError:
        pass

if __name__ == "__main__":
    solve()

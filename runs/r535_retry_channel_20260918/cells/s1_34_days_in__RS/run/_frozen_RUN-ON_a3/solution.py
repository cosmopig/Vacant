import datetime

def solve():
    try:
        line = input().split()
        if not line:
            return
        year = int(line[0])
        month = int(line[1])
        
        # Use a dummy day (1) to get the first day of the month
        # Then find the last day by going to the next month and subtracting one day
        if month == 12:
            next_month = datetime.date(year + 1, 1, 1)
        else:
            next_month = datetime.date(year, month + 1, 1)
            
        last_day = (next_month - datetime.timedelta(days=1)).day
        print(last_day)
    except EOFError:
        pass

if __name__ == "__main__":
    solve()

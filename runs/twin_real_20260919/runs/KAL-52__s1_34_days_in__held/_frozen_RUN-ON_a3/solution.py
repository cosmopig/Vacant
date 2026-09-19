import datetime
import sys

def solve():
    if len(sys.argv) < 3:
        return
    try:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        
        if month == 12:
            next_month = datetime.date(year + 1, 1, 1)
        else:
            next_month = datetime.date(year, month + 1, 1)
            
        last_day = (next_month - datetime.timedelta(days=1)).day
        print(last_day)
    except ValueError:
        pass

if __name__ == "__main__":
    solve()

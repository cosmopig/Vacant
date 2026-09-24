import datetime
import sys

def solve():
    if len(sys.argv) < 3:
        return
    try:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        
        if month == 12:
            next_date = datetime.date(year + 1, 1, 1)
        else:
            next_date = datetime.date(year, month + 1, 1)
            
        current_date = datetime.date(year, month, 1)
        print((next_date - current_date).days)
    except ValueError:
        pass

if __name__ == "__main__":
    solve()

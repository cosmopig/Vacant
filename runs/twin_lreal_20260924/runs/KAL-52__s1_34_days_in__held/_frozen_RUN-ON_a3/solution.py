import datetime
import sys

def solve():
    # The problem states "The year is the first argument and the month is the second".
    # In many coding environments, this refers to command-line arguments.
    # However, if it's a standard competitive programming task, it might mean stdin.
    # Let's check sys.argv first.
    if len(sys.argv) >= 3:
        try:
            year = int(sys.argv[1])
            month = int(sys.argv[2])
        except ValueError:
            return
    else:
        line = sys.stdin.readline()
        if not line:
            return
        parts = line.split()
        if len(parts) < 2:
            return
        try:
            year = int(parts[0])
            month = int(parts[1])
        except ValueError:
            return

    # Calculate last day of the month
    if month == 12:
        next_month = datetime.date(year + 1, 1, 1)
    else:
        next_month = datetime.date(year, month + 1, 1)
        
    last_day = (next_month - datetime.timedelta(days=1)).day
    print(last_day)

if __name__ == "__main__":
    solve()

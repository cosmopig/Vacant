import sys

def solve():
    line = sys.stdin.read().split()
    if not line:
        return
    year = int(line[0])
    month = int(line[1])
    
    # Days in each month (non-leap year)
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    # Check for leap year
    is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
    
    if month == 2 and is_leap:
        print(29)
    else:
        print(days_in_month[month - 1])

if __name__ == "__main__":
    solve()

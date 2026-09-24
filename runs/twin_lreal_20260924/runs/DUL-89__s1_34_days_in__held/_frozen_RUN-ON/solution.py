import sys

def solve():
    line = sys.stdin.read().split()
    if not line:
        return
    year = int(line[0])
    month = int(line[1])
    
    # Days in each month for a non-leap year
    days_in_months = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    # Check for leap year
    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    
    if is_leap:
        days_in_months[1] = 29
        
    print(days_in_months[month - 1])

if __name__ == "__main__":
    solve()

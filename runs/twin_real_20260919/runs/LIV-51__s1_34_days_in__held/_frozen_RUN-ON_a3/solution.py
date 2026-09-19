import sys
from calendar import monthrange

def main():
    if len(sys.argv) >= 3:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
    else:
        line = sys.stdin.readline()
        if not line:
            return
        parts = line.split()
        if len(parts) < 2:
            return
        year = int(parts[0])
        month = int(parts[1])

    # monthrange returns (first_day_of_week, number_of_days_in_month)
    _, days = monthrange(year, month)
    print(days)

if __name__ == "__main__":
    main()

import sys

def days_in_month(year, month):
    if month == 2:
        # Leap year rule: divisible by 4, but not by 100 unless also divisible by 400
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            return 29
        else:
            return 28
    elif month in [4, 6, 9, 11]:
        return 30
    else:
        return 31

if __name__ == "__main__":
    if len(sys.argv) == 3:
        try:
            year = int(sys.argv[1])
            month = int(sys.argv[2])
            print(days_in_month(year, month))
        except ValueError:
            pass

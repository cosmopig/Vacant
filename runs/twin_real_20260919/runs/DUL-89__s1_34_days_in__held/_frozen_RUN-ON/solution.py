def is_leap(year):
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    if year % 4 == 0:
        return True
    return False

def days_in_month(year, month):
    if month in [1, 3, 5, 7, 8, 10, 12]:
        return 31
    elif month == 2:
        return 29 if is_leap(year) else 28
    elif month in [4, 6, 9, 11]:
        return 30
    else:
        return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        print(days_in_month(year, month))

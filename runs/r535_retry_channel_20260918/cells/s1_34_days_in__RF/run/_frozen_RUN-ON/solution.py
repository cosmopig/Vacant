import datetime

def days_in_month(year, month):
    # The datetime module handles leap years correctly for February.
    # We can use the last day of the next month minus one day, 
    # or just use calendar.monthrange which is more direct.
    import calendar
    _, num_days = calendar.monthrange(year, month)
    return num_days

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        try:
            year = int(sys.argv[1])
            month = int(sys.argv[2])
            print(days_in_month(year, month))
        except ValueError:
            pass

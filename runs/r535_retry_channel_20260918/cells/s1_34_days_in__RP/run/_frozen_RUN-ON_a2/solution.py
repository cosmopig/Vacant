def days_in(year, month):
    # February is special
    if month == 2:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            return 29
        else:
            return 28
    
    # April, June, September, November have 30 days
    if month in [4, 6, 9, 11]:
        return 30
    
    # All other months have 31 days
    return 31

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        print(days_in(year, month))

import datetime
import sys

def main():
    if len(sys.argv) < 3:
        return
    
    try:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        
        # Calculate the first day of the current month
        current_date = datetime.date(year, month, 1)
        
        # Calculate the first day of the next month
        if month == 12:
            next_date = datetime.date(year + 1, 1, 1)
        else:
            next_date = datetime.date(year, month + 1, 1)
            
        # The difference in days is the number of days in the current month
        print((next_date - current_date).days)
    except ValueError:
        pass

if __name__ == "__main__":
    main()

import sys
import calendar

def main():
    if len(sys.argv) < 3:
        return
    
    try:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        
        # calendar.monthrange returns a tuple (first_day_of_week, number_of_days_in_month)
        _, days_in_month = calendar.monthrange(year, month)
        print(days_in_month)
    except ValueError:
        pass

if __name__ == "__main__":
    main()

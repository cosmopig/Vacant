def is_leap(y):
    if y < 1:
        raise ValueError("Year must be 1 or greater.")
    
    # A year is a leap year if it's divisible by 4, 
    # except for years that are divisible by 100 but not by 400.
    if (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0):
        return True
    else:
        return False

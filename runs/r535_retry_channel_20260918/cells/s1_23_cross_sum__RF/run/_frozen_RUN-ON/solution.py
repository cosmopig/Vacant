def sum_digits(n):
    """
    Adds together the individual digits of a non-negative whole number 
    and returns the total as a whole number.
    """
    return sum(int(digit) for digit in str(abs(n)))

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        try:
            num = int(sys.argv[1])
            print(sum_digits(num))
        except ValueError:
            pass

def sum_digits(n):
    """
    Adds together the individual digits of a whole number that is never negative,
    and gives back the total as a whole number.
    """
    return sum(int(digit) for digit in str(n))

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        num = int(sys.argv[1])
        print(sum_digits(num))

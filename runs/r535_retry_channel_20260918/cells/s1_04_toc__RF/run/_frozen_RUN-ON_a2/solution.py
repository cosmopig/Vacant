def to_c(fahrenheit):
    return round((fahrenheit - 32) * 5 / 9, 1)

if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        try:
            f_temp = float(line.strip())
            print(to_c(f_temp))
        except ValueError:
            pass

def to_c(fahrenheit):
    celsius = (fahrenheit - 32) * 5 / 9
    return round(celsius, 1)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        try:
            f_temp = float(sys.argv[1])
            print(to_c(f_temp))
        except ValueError:
            pass

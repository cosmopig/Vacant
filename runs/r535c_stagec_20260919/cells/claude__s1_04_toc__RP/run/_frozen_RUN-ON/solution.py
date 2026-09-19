def fahrenheit_to_celsius(fahrenheit: float) -> float:
    celsius = (fahrenheit - 32) * 5 / 9
    return round(celsius, 1)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        try:
            f_val = float(sys.argv[1])
            print(fahrenheit_to_celsius(f_val))
        except ValueError:
            pass

import sys

def fahrenheit_to_celsius(fahrenheit):
    celsius = (fahrenheit - 32) * 5 / 9
    return round(celsius, 1)

if __name__ == "__main__":
    for line in sys.stdin:
        try:
            f_val = float(line.strip())
            print(fahrenheit_to_celsius(f_val))
        except ValueError:
            pass

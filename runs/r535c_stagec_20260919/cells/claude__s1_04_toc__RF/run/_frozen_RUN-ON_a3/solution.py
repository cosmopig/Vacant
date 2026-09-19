def fahrenheit_to_celsius(fahrenheit: float) -> float:
    celsius = (fahrenheit - 32) * 5 / 9
    return round(celsius, 1)

if __name__ == "__main__":
    try:
        f_input = input().strip()
        if f_input:
            fahrenheit = float(f_input)
            print(fahrenheit_to_celsius(fahrenheit))
    except EOFError:
        pass
    except ValueError:
        pass

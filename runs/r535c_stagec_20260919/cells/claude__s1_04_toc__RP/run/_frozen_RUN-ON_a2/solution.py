def to_c(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius, rounded to one decimal place."""
    celsius = (fahrenheit - 32) * 5 / 9
    return round(celsius, 1)

if __name__ == "__main__":
    # Example usage
    print(to_c(32))  # Expected: 0.0
    print(to_c(212)) # Expected: 100.0

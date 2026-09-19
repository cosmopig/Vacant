def pin(value, lower_edge, upper_edge):
    if lower_edge <= value <= upper_edge:
        return value
    elif value < lower_edge:
        return lower_edge
    else:
        return upper_edge

# Example usage (optional, but good for testing)
if __name__ == "__main__":
    print(pin(5, 1, 10))   # Expected: 5
    print(pin(0, 1, 10))   # Expected: 1
    print(pin(11, 1, 10))  # Expected: 10

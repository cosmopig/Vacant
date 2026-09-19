def size_label(n):
    """
    Turns a count of bytes into a short label for a user interface, 
    using the units B, KB, MB and GB and stopping at the largest unit 
    the number reaches.
    """
    if n < 1024:
        return f"{n} B"
    elif n < 1024**2:
        return f"{n / 1024:.1f} KB"
    elif n < 1024**3:
        return f"{n / (1024**2):.1f} MB"
    else:
        return f"{n / (1024**3):.1f} GB"

# Example usage and testing
if __name__ == "__main__":
    test_cases = [
        (500, "500 B"),
        (1024, "1.0 KB"),
        (1048576, "1.0 MB"),
        (1073741824, "1.0 GB"),
    ]
    for val, expected in test_cases:
        result = size_label(val)
        print(f"Input: {val}, Expected: {expected}, Got: {result}")

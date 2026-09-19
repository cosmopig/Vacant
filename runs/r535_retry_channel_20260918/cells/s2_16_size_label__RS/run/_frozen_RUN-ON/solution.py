def size_label(n):
    """
    Turns a count of bytes into a short label for a user interface, 
    using the units B, KB, MB and GB and stopping at the largest unit 
    the number reaches. Labels are formatted to line up consistently.
    """
    if n < 1024:
        return f"{n:>7} B"
    elif n < 1024**2:
        return f"{n/1024:>7.1f} KB"
    elif n < 1024**3:
        return f"{n/1024**2:>7.1f} MB"
    else:
        return f"{n/1024**3:>7.1f} GB"

if __name__ == "__main__":
    # Test cases
    print(size_label(500))          # Expected: "   500 B"
    print(size_label(1024))         # Expected: "  1.0 KB"
    print(size_label(1048576))      # Expected: "   1.0 MB"
    print(size_label(1073741824))   # Expected: "   1.0 GB"

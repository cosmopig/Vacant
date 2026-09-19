def size_label(n):
    """
    Turns a count of bytes into a short label for a user interface, 
    using the units B, KB, MB and GB and stopping at the largest unit 
    the number reaches. Labels are padded to align consistently in a column.
    """
    if n < 1024:
        return f"{n:>7} B"
    elif n < 1024**2:
        return f"{n/1024:>7.1f} KB"
    elif n < 1024**3:
        return f"{n/1024**2:>7.1f} MB"
    else:
        return f"{n/1024**3:>7.1f} GB"

# Examples of usage (not required by task but good for verification):
# print(size_label(500))          # 500 B
# print(size_label(1024))         # 1.0 KB
# print(size_label(1048576))      # 1.0 MB
# print(size_label(1073741824))   # 1.0 GB

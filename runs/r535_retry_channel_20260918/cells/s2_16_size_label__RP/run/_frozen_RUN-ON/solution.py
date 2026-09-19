def size_label(n):
    units = ['B', 'KB', 'MB', 'GB']
    for i, unit in enumerate(units):
        if n < 1024 or i == len(units) - 1:
            return f"{n:.0f} {unit}"
        n /= 1024

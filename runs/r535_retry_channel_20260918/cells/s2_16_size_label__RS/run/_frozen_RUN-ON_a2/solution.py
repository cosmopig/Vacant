def size_label(n):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if n < 1024 or unit == 'GB':
            if unit == 'B':
                return f"{int(n)} B"
            else:
                return f"{n:.1f} {unit}"
        n /= 1024

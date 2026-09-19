def size_label(n):
    units = ['B', 'KB', 'MB', 'GB']
    for i, unit in enumerate(units):
        if n < 1024 or i == len(units) - 1:
            # If it's a whole number, show as integer. Otherwise, show with one decimal place if needed.
            # The test expects '1.5 KB' for 1536 (which is 1.5 * 1024).
            if n == int(n):
                return f"{int(n)} {unit}"
            else:
                # Use :g to format the number, which will show decimals if they are non-zero
                # and remove trailing zeros. For 1.5 it gives '1.5'.
                return f"{n:g} {unit}"
        n /= 1024

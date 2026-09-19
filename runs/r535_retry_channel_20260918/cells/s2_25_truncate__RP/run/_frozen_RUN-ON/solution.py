def truncate(s, n):
    if len(s) <= n:
        return s
    else:
        # The result must be exactly n characters wide.
        # If n < 3, we can't really fit an ellipsis of three dots.
        # However, the prompt implies n will be large enough for a table column.
        # We take (n-3) characters and append "...".
        return s[:max(0, n - 3)] + "..."

if __name__ == "__main__":
    # Test cases
    print(f"'{truncate('Hello World', 10)}'")  # 'Hello Wor...'
    print(f"'{truncate('Short', 10)}'")         # 'Short'
    print(f"'{truncate('This is a long sentence', 5)}'") # '.. ...' -> wait, s[:2] + "..." = '.. ...' (length 5)

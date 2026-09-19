def truncate(s, n):
    if len(s) <= n:
        return s
    else:
        # If n is very small (e.g., < 3), we might need to handle it differently,
        # but the prompt implies a standard ellipsis of three dots.
        # For n=10, "Hello World" -> "Hello Wor..." (length 10)
        return s[:max(0, n - 3)] + "..."

if __name__ == "__main__":
    # Test cases
    print(f"'{truncate('Hello World', 10)}'")  # Expected: 'Hello Wor...' (length 10)
    print(f"'{truncate('Short', 10)}'")        # Expected: 'Short'
    print(f"'{truncate('This is a long sentence', 5)}'") # Expected: 'Th...' (length 5)

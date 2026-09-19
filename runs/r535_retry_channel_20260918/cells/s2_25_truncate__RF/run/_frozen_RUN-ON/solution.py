def truncate(s, n):
    if len(s) <= n:
        return s
    else:
        return s[:n-3] + "..."

# Examples to verify (optional but good for testing)
if __name__ == "__main__":
    print(f"'{truncate('Hello World', 10)}'")  # Expected: 'Hello Wor...'
    print(f"'{truncate('Short', 10)}'")        # Expected: 'Short'
    print(f"'{truncate('This is a long sentence.', 5)}'") # Expected: 'Th...'

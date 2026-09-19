def truncate(s, n):
    if len(s) <= n:
        return s
    # The prompt says the three dots count towards n.
    # If n < 3 and we need to truncate, it's technically impossible to fit "..."
    # but usually these problems assume n >= 3 for truncation cases.
    if n < 3:
        return s[:n]
    return s[:n-3] + "..."

if __name__ == "__main__":
    # Test cases
    print(f"'{truncate('Hello World', 10)}'")      # Expected: 'Hello Wor...' (length 10)
    print(f"'{truncate('Hello', 10)}'")            # Expected: 'Hello'
    print(f"'{truncate('A very long string', 5)}'") # Expected: 'A..' (Wait, s[:2] + "..." is length 5)
    print(f"'{truncate('Short', 3)}'")             # Expected: '...'

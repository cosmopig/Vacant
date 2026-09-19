def rle(s):
    if not s:
        return []
    
    result = []
    count = 1
    for i in range(1, len(s)):
        if s[i] == s[i-1]:
            count += 1
        else:
            result.append((s[i-1], count))
            count = 1
    result.append((s[-1], count))
    return result

# Example usage (optional, for testing):
if __name__ == "__main__":
    test_cases = [
        ("aaabbc", [('a', 3), ('b', 2), ('c', 1)]),
        ("abcde", [('a', 1), ('b', 1), ('c', 1), ('d', 1), ('e', 1)]),
        ("", []),
        ("aaaaa", [('a', 5)]),
    ]
    for s, expected in test_cases:
        assert rle(s) == expected

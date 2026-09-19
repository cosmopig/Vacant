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

# Example usage (optional, but good for testing):
if __name__ == "__main__":
    test_input = "aaabbccccd"
    print(rle(test_input))  # Expected: [('a', 3), ('b', 2), ('c', 4), ('d', 1)]

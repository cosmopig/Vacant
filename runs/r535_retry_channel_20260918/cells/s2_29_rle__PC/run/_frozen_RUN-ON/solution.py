def rle(s):
    if not s:
        return []
    
    result = []
    i = 0
    while i < len(s):
        char = s[i]
        count = 0
        while i < len(s) and s[i] == char:
            count += 1
            i += 1
        result.append((char, count))
    return result

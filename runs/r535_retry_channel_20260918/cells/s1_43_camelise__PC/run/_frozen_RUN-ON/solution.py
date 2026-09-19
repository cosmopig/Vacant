def camelise(s: str) -> str:
    words = [w for w in s.split('_') if w]
    if not words:
        return ""
    
    res = words[0].lower()
    for i in range(1, len(words)):
        res += words[i].capitalize()
    return res

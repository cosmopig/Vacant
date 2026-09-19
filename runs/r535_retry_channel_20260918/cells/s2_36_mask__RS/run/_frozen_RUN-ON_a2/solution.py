def mask(s, keep):
    if len(s) <= keep:
        return s
    
    res = s[:keep]
    masked_part = s[keep:]
    
    # "replacing every other character with one single mask character"
    # This means for every 2 characters in the masked part, we replace them with 1 '*'.
    for i in range(0, len(masked_part), 2):
        res += "*"
        
    return res

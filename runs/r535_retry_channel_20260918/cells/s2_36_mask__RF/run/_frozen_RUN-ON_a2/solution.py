def mask(s, keep):
    if len(s) <= keep:
        return s
    
    result = s[:keep]
    remaining = s[keep:]
    masked_part = ""
    for i in range(0, len(remaining), 2):
        masked_part += "*"
    return result + masked_part

def mask(s, keep):
    if len(s) <= keep:
        return s

    result = list(s[:keep])
    for i in range(keep, len(s)):
        # The requirement is "replacing every other character with one single mask character".
        # This usually means the characters at indices keep+1, keep+3, keep+5... are replaced by '*'.
        if (i - keep) % 2 != 0:
            result.append('*')
        else:
            result.append(s[i])
    return "".join(result)

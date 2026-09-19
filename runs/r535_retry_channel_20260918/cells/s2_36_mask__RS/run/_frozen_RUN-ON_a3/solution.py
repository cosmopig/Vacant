def mask(s, keep):
    """
    Hides most of a piece of text, leaving `keep` of its characters readable 
    and replacing every other character with one single mask character.
    """
    if len(s) <= keep:
        return s

    result = list(s[:keep])
    for i in range(keep, len(s)):
        # "replacing every other character" can be interpreted as 
        # replacing characters at indices 0, 2, 4... of the masked part.
        if (i - keep) % 2 == 0:
            result.append('*')
        else:
            result.append(s[i])
    return "".join(result)

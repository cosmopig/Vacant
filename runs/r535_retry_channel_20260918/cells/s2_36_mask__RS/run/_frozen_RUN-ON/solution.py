def mask(s, keep):
    if len(s) <= keep:
        return s

    result = s[:keep]
    remaining = s[keep:]
    masked_part = ""
    for i in range(0, len(remaining), 2):
        # "replacing every other character with one single mask character"
        # This means for each pair of characters, we replace them with a single '*'
        if i + 1 < len(remaining):
            masked_part += "*"
        else:
            # If there's only one character left at the end, it doesn't have an "other"
            # to form a pair. The prompt says "replacing every other", which implies pairs.
            # However, if we want to be safe and ensure all characters are accounted for, 
            # we could also mask it or keep it. Given the context of card numbers, 
            # keeping it might be safer if it's a single trailing char.
            masked_part += remaining[i]

    return result + masked_part

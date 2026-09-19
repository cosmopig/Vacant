def mask(s, keep):
    if keep >= len(s):
        return s

    masked_part = s[:len(s) - keep]
    readable_part = s[len(s) - keep:]

    # "replacing every other character with one single mask character"
    # This means for every 2 characters in the masked part, we replace them with a single '*'.
    # If there's an odd number of characters at the end of the masked part, 
    # it also gets replaced by a single '*' because "every other" implies pairs.
    # Actually, let's re-read: "replacing every other character with one single mask character".
    # This could mean:
    # Input:  A B C D E F G
    # Output: * * * * (if we replace each pair)
    # Or it could mean:
    # Input:  A B C D E F G
    # Output: A * C * E * G (this doesn't "hide most")
    
    # Let's try the simplest interpretation of "replacing every other character with one single mask character":
    # For each pair of characters, we replace them with a single '*'.
    # This means for length L, we get ceil(L/2) masks.
    
    res = ""
    for i in range(0, len(masked_part), 2):
        res += "*"
    
    return res + readable_part

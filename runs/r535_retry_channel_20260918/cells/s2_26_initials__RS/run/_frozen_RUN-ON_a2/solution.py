def initials(name):
    parts = name.split(' ')
    initials_list = []
    for part in parts:
        # Compound names joined by punctuation (e.g., "Jean-Pierre") 
        # should have both halves treated as separate parts for initials.
        import re
        sub_parts = re.split(r'[-.,;:]', part)
        for sub in sub_parts:
            if sub:
                initials_list.append(sub[0].upper())
    return "".join(initials_list)

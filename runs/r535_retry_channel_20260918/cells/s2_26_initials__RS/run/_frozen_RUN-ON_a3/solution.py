import re

def initials(name):
    # The parts of a name are separated by spaces.
    parts = name.split(' ')
    initials_list = []
    for part in parts:
        if not part:
            continue
        # Compound given names joined by punctuation marks (e.g., Jean-Luc, O'Connor)
        # both halves are part of how someone is addressed.
        # We split the part by common punctuation marks used in names.
        sub_parts = re.split(r'[-.,\']', part)
        for sub in sub_parts:
            if sub and sub[0].isalpha():
                initials_list.append(sub[0].upper())
    return "".join(initials_list)

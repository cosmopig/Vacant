import re

def initials(name):
    # The parts of a name are separated by spaces.
    parts = name.split(' ')
    result = []
    for part in parts:
        if not part:
            continue
        # Compound given names joined by a punctuation mark are common 
        # and both halves are part of how someone is addressed.
        # We split by any non-alphanumeric character to catch these.
        sub_parts = re.split(r'[^a-zA-Z0-9]', part)
        for sub in sub_parts:
            if sub:
                result.append(sub[0].upper())
    return "".join(result)

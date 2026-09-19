import re

def initials(name):
    parts = name.split(' ')
    result = []
    for part in parts:
        if not part:
            continue
        sub_parts = re.split(r'[^a-zA-Z0-9]', part)
        for sp in sub_parts:
            if sp:
                result.append(sp[0].upper())
    return "".join(result)

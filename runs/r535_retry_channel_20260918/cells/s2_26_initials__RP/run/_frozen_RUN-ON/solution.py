import re

def initials(name):
    # The parts of a name are separated by spaces.
    parts = name.split(' ')
    initials_list = []
    for part in parts:
        if not part:
            continue
        # Compound given names joined by punctuation marks (e.g., "Jean-Pierre")
        # both halves are part of how someone is addressed, so we take the first letter 
        # of each segment separated by common punctuation marks.
        segments = re.split(r'[-.,;:]', part)
        for segment in segments:
            if segment:
                initials_list.append(segment[0].upper())
    return "".join(initials_list)

import re

def initials(name):
    # The parts of a name are separated by spaces.
    # Compound given names joined by a punctuation mark are common 
    # and both halves are part of how someone is addressed.
    # This means we should treat any sequence of letters/numbers as a "part" 
    # regardless of whether they are separated by space or punctuation.
    words = re.findall(r'[a-zA-Z0-9]+', name)
    return ".".join(word[0].upper() for word in words) + "."

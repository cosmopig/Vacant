def initials(full_name):
    return "".join(p[0].upper() for p in full_name.split())

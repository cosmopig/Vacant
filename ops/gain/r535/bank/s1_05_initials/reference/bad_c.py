def get_initials(full_name):
    return [p[0].upper() for p in full_name.split()]

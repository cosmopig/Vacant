def initials(full_name: str) -> str:
    """
    Takes a person's full name and returns the initial of each part.
    The parts are separated by spaces. The result is a sequence of
    single upper-case characters, one per part, in order.
    """
    parts = full_name.split()
    return "".join(part[0].upper() for part in parts if part)


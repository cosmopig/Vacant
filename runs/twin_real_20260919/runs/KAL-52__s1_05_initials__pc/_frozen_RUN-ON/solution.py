def initials(full_name: str) -> list[str]:
    """
    Takes a person's full name and pulls out the initial of each part of it.
    The parts of a name are separated by spaces.

    Returns them as a sequence of single upper-case characters, one per
    part, in the order the parts appear.
    """
    return [part[0].upper() for part in full_name.split() if part]

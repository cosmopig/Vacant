def initials(full_name: str) -> list[str]:
    """
    Takes a person's full name and pulls out the initial of each part of it.
    The parts of a name are separated by spaces.

    Args:
        full_name (str): The full name to extract initials from.

    Returns:
        list[str]: A sequence of single upper-case characters, one per part, 
                   in the order the parts appear.
    """
    parts = full_name.split()
    return [part[0].upper() for part in parts if part]

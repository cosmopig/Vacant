def get_initials(full_name: str) -> str:
    """
    Takes a person's full name and returns the initial of each part.
    The parts are separated by spaces.
    Returns a sequence of single upper-case characters.
    """
    parts = full_name.split()
    initials = [part[0].upper() for part in parts if part]
    return "".join(initials)

if __name__ == "__main__":
    # Example usage:
    # print(get_initials("John Doe"))  # Output: "JD"
    pass

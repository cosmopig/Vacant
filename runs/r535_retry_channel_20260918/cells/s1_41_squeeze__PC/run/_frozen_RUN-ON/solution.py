def squeeze(s: str) -> str:
    """
    Tidy a piece of text so that every run of whitespace inside it
    becomes one single space, and so that there is no whitespace left at the start
    or at the end.

    Args:
        s (str): The input string to tidy.

    Returns:
        str: The tidied string.
    """
    # split() without arguments splits by any whitespace and discards empty strings
    # join() then joins them with a single space
    return " ".join(s.split())

def n_words(text: str) -> int:
    """
    Report how many words a line of text contains.
    Words are separated by runs of whitespace. Whitespace at the start or the end
    of the line does not create extra words, and a line made of nothing but
    whitespace contains none at all.
    """
    return len(text.split())

def normalize(p):
    """
    Tidies a forward-slash path: a run of separators
    becomes a single separator.
    """
    import re
    return re.sub(r'/+', '/', p)

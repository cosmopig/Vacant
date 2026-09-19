def normalize(p):
    """
    Tidies a forward-slash path: a run of separators
    becomes a single separator.
    """
    import re
    res = re.sub(r'/+', '/', p)
    if len(res) > 1 and res.endswith('/'):
        return res[:-1]
    return res

def normalize(p):
    # Replace multiple consecutive slashes with a single slash
    import re
    return re.sub(r'/+', '/', p)

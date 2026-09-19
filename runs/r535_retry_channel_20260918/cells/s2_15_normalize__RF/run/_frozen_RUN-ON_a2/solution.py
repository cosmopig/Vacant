import re

def normalize(p: str) -> str:
    """
    Tidies a forward-slash path: a run of separators becomes a single separator.
    """
    return re.sub(r'/+', '/', p)

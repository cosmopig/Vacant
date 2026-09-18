def to_int(s):
    if not isinstance(s, str):
        raise TypeError("to_int wants text")
    return int(s.strip())

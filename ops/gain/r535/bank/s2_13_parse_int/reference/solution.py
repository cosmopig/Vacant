def parse_int(s):
    if not isinstance(s, str):
        raise TypeError("parse_int wants text")
    return int(s.strip())

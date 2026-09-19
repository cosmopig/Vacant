def trim_zeros(s):
    if "." not in s:
        return s
    s = s.rstrip("0")
    if s.endswith("."):
        s = s[:-1]
    return s

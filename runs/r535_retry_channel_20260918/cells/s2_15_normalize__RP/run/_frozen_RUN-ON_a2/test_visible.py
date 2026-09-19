def normalize(p):
    """
    Tidies a forward-slash path: a run of separators
    becomes a single separator.
    """
    import re
    return re.sub(r'/+', '/', p)

def check_01_normalize():
    args = ('a//b/',)
    got = normalize(args[0])
    want = 'a/b'
    assert got == want, "normalize args=%r got=%r want=%r" % (args, got, want)

if __name__ == "__main__":
    check_01_normalize()

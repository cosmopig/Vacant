def wrap(s, width):
    words = s.split()
    if not words:
        return []

    res = []
    curr_line = []
    curr_len = 0

    for word in words:
        space = 1 if curr_line else 0
        if not curr_line:
            curr_line.append(word)
            curr_len = len(word)
        else:
            if curr_len + space + len(word) > width:
                res.append(" ".join(curr_line))
                curr_line = [word]
                curr_len = len(word)
            else:
                curr_line.append(word)
                curr_len += space + len(word)

    if curr_line:
        res.append(" ".join(curr_line))
    return res

def test_wrap():
    # Test case from feedback
    args = ('enormous', 3)
    got = wrap(*args)
    want = ['enormous']
    assert got == want, "wrap args=%r got=%r want=%r" % (args, got, want)

if __name__ == "__main__":
    test_wrap()

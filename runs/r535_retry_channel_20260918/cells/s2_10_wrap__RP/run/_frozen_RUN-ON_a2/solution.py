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

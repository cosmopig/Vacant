def wrap(s, width):
    words = s.split()
    if not words:
        return []

    res = []
    curr_line = []
    curr_len = 0

    for word in words:
        # If the word itself is longer than the width, we must break it into pieces.
        if len(word) > width:
            # If there's a pending line, finish it first.
            if curr_line:
                res.append(" ".join(curr_line))
                curr_line = []
                curr_len = 0

            # Break the word into chunks of 'width'
            i = 0
            while i < len(word):
                chunk = word[i : i + width]
                if len(chunk) == width:
                    res.append(chunk)
                else:
                    # Last piece of a long word
                    curr_line.append(chunk)
                    curr_len = len(chunk)
                    break
                i += width
        else:
            # Word fits or doesn't fit in current line
            space = 1 if curr_line else 0
            if curr_len + space + len(word) <= width:
                curr_line.append(word)
                curr_len += space + len(word)
            else:
                res.append(" ".join(curr_line))
                curr_line = [word]
                curr_len = len(word)

    if curr_line:
        res.append(" ".join(curr_line))
    return res

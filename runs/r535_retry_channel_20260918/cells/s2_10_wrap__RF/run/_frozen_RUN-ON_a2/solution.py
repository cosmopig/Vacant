def wrap(s, width):
    words = s.split()
    if not words:
        return []

    res = []
    current_line = ""

    for word in words:
        # If the current line is empty, just add the word (or part of it)
        if not current_line:
            if len(word) <= width:
                current_line = word
            else:
                # Word is longer than width, must break it
                while len(word) > width:
                    res.append(word[:width])
                    word = word[width:]
                current_line = word
        else:
            # Try to add space + word
            if len(current_line) + 1 + len(word) <= width:
                current_line += " " + word
            else:
                # Cannot fit on current line, push current line and handle word
                res.append(current_line)
                if len(word) <= width:
                    current_line = word
                else:
                    while len(word) > width:
                        res.append(word[:width])
                        word = word[width:]
                    current_line = word

    if current_line:
        res.append(current_line)

    return res

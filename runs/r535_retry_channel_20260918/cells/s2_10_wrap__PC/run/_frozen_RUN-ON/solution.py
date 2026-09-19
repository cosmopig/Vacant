def wrap(s, width):
    words = s.split()
    if not words:
        return []

    result = []
    current_line = []
    current_length = 0

    for word in words:
        # If the word itself is longer than width, it gets its own piece
        if len(word) > width:
            if current_line:
                result.append(" ".join(current_line))
                current_line = []
                current_length = 0
            result.append(word)
            continue

        # Check if adding this word (plus a space if not the first word in line) exceeds width
        space = 1 if current_line else 0
        if current_length + space + len(word) <= width:
            current_line.append(word)
            current_length += space + len(word)
        else:
            # Current word doesn't fit, so join the current line and start a new one
            result.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)

    if current_line:
        result.append(" ".join(current_line))

    return result

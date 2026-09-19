def wrap(s, width):
    words = s.split()
    if not words:
        return []

    result = []
    current_line = []
    current_length = 0

    for word in words:
        if len(word) > width:
            # If there's a current line being built, finish it first
            if current_line:
                result.append(" ".join(current_line))
                current_line = []
                current_length = 0

            # Break the long word into pieces of exactly 'width' length
            for i in range(0, len(word), width):
                piece = word[i:i+width]
                result.append(piece)
        else:
            if not current_line:
                current_line = [word]
                current_length = len(word)
            else:
                # +1 for the space between words in a piece
                if current_length + 1 + len(word) <= width:
                    current_line.append(word)
                    current_length += 1 + len(word)
                else:
                    result.append(" ".join(current_line))
                    current_line = [word]
                    current_length = len(word)

    if current_line:
        result.append(" ".join(current_line))

    return result

def wrap_text(text, width):
    words = text.split()
    pieces = []
    current_piece = []
    current_length = 0

    for word in words:
        if len(word) > width:
            if current_piece:
                pieces.append(" ".join(current_piece))
                current_piece = []
                current_length = 0
            pieces.append(word)
            continue

        space = 1 if current_piece else 0
        if current_length + space + len(word) <= width:
            current_piece.append(word)
            current_length += space + len(word)
        else:
            pieces.append(" ".join(current_piece))
            current_piece = [word]
            current_length = len(word)

    if current_piece:
        pieces.append(" ".join(current_piece))

    return pieces

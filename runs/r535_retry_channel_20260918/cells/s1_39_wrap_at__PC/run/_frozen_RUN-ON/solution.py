def wrap_at(s: str, width: int) -> list[str]:
    """
    Break a line of text into pieces no longer than a given width,
    breaking only between words.

    A word longer than the width goes on a piece of its own and is never cut in
    half. Words are separated by whitespace on the way in and by a single space
    inside a piece. The pieces come back in order, gathered together.
    """
    words = s.split()
    if not words:
        return []

    pieces = []
    current_piece = []
    current_length = 0

    for word in words:
        word_len = len(word)
        
        # If the word itself is longer than the width, it must be its own piece.
        if word_len > width:
            if current_piece:
                pieces.append(" ".join(current_piece))
                current_piece = []
                current_length = 0
            pieces.append(word)
            continue

        # Check if adding this word (plus a space if not the first word in piece) exceeds width
        space_needed = 1 if current_piece else 0
        if current_length + space_needed + word_len <= width:
            current_piece.append(word)
            current_length += space_needed + word_len
        else:
            # Current piece is full, save it and start a new one with the current word
            pieces.append(" ".join(current_piece))
            current_piece = [word]
            current_length = word_len

    if current_piece:
        pieces.append(" ".join(current_piece))

    return pieces

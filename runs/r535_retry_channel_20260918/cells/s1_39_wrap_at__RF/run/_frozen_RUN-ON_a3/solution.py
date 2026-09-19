def wrap_text(text, width):
    words = text.split()
    pieces = []
    current_piece = []
    current_length = 0

    for word in words:
        # If the word itself is longer than the width, it gets its own piece
        if len(word) > width:
            if current_piece:
                pieces.append(" ".join(current_piece))
                current_piece = []
                current_length = 0
            pieces.append(word)
            continue

        # Check if adding this word (plus a space if not the first word in piece) exceeds width
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

# Example usage (optional, for testing):
# print(wrap_text("This is a test sentence to see how the wrapping works.", 10))

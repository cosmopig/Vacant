def wrap_text(text, width):
    words = text.split()
    pieces = []
    current_piece = ""

    for word in words:
        if len(word) > width:
            # If there's a current piece being built, save it first
            if current_piece:
                pieces.append(current_piece.strip())
                current_piece = ""
            # The long word goes on its own piece
            pieces.append(word)
        else:
            if not current_piece:
                current_piece = word
            elif len(current_piece) + 1 + len(word) <= width:
                current_piece += " " + word
            else:
                pieces.append(current_piece.strip())
                current_piece = word

    if current_piece:
        pieces.append(current_piece.strip())

    return pieces

# Example usage (optional, for testing):
# print(wrap_text("This is a long sentence that should be wrapped.", 10))

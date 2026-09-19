def wrap(s, width):
    words = s.split()
    if not words:
        return []

    result = []
    current_line = []
    current_len = 0

    for word in words:
        # If the word itself is longer than the width, it must be broken into pieces of length 'width'
        if len(word) > width:
            # Flush current line if not empty
            if current_line:
                result.append(" ".join(current_line))
                current_line = []
                current_len = 0
            
            # Break the long word into pieces of exactly 'width'
            for i in range(0, len(word), width):
                piece = word[i:i+width]
                if len(piece) == width:
                    result.append(piece)
                else:
                    # Last piece of a broken long word
                    current_line = [piece]
                    current_len = len(piece)
        else:
            # Normal word handling
            space = 1 if current_line else 0
            if current_len + space + len(word) <= width:
                current_line.append(word)
                current_len += space + len(word)
            else:
                result.append(" ".join(current_line))
                current_line = [word]
                current_len = len(word)

    if current_line:
        result.append(" ".join(current_line))

    return result

def wrap(s, width):
    words = s.split()
    if not words:
        return []

    result = []
    current_line = []
    current_len = 0

    for word in words:
        # If the word itself is longer than the width, it must be broken into pieces
        if len(word) > width:
            # Flush current line first
            if current_line:
                result.append(" ".join(current_line))
                current_line = []
                current_len = 0
            
            # Break the long word into pieces of length 'width'
            # Note: The prompt says "breaking between words", but also "no piece comes out longer than width".
            # If a single word is > width, it MUST be broken.
            for i in range(0, len(word), width):
                piece = word[i : i + width]
                result.append(piece)
        else:
            # Normal word handling
            space = 1 if current_line else 0
            if current_len + space + len(word) <= width:
                current_line.append(word)
                current_len += space + len(word)
            else:
                # Flush current line and start new one with the word
                result.append(" ".join(current_line))
                current_line = [word]
                current_len = len(word)

    if current_line:
        result.append(" ".join(current_line))

    return result

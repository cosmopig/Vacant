def wrap(s, width):
    words = s.split()
    if not words:
        return []

    result = []
    current_line = []
    current_len = 0

    for word in words:
        # If the word itself is longer than the allowed width, it must be broken into pieces of length 'width'
        if len(word) > width:
            # Flush current line first
            if current_line:
                result.append(" ".join(current_line))
                current_line = []
                current_len = 0
            
            # Break the long word into pieces of length 'width'
            i = 0
            while i < len(word):
                chunk = word[i:i+width]
                if len(chunk) == width and i + width < len(word):
                    result.append(chunk)
                    i += width
                else:
                    # This is the last piece of this long word
                    current_line = [chunk]
                    current_len = len(chunk)
                    break # Break while loop, continue to next word in for loop

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

def wrap(s, width):
    words = s.split()
    if not words:
        return []

    result = []
    current_line = []
    current_len = 0

    for word in words:
        if len(word) > width:
            if current_line:
                result.append(" ".join(current_line))
                current_line = []
                current_len = 0
            
            i = 0
            while i < len(word):
                chunk = word[i:i+width]
                result.append(chunk)
                i += width
        else:
            space = 1 if current_line else 0
            if current_len + space + len(word) > width:
                result.append(" ".join(current_line))
                current_line = [word]
                current_len = len(word)
            else:
                current_line.append(word)
                current_len += space + len(word)

    if current_line:
        result.append(" ".join(current_line))
    
    return result

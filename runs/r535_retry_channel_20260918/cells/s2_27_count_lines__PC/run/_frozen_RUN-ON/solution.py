def count_lines(text):
    if not text:
        return 0
    
    # If it ends with a newline, remove only the very last one.
    if text.endswith('\n'):
        text = text[:-1]
        
    lines = text.split('\n')
    return len(lines)

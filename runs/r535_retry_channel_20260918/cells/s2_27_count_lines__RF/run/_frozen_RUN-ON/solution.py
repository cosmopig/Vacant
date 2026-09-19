def count_lines(text):
    if not text:
        return 0
    return len(text.splitlines())

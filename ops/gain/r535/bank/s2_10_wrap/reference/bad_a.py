def wrap(s, width):
    joined = " ".join(s.split())
    return [joined[i:i + width] for i in range(0, len(joined), width)]

def page(items, number, size):
    if number < 1 or size < 1:
        raise ValueError("page number and size must be at least one")
    start = (number - 1) * size
    return items[start:start + size]

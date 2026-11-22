def page(items, number, size):
    if number < 1 or size < 1:
        raise ValueError('positive page and size required')
    start = (number - 1) * size
    return items[start:start + size]

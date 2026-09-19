def pin(value, lower_edge, upper_edge):
    if lower_edge <= value <= upper_edge:
        return value
    elif value < lower_edge:
        return lower_edge
    else:
        return upper_edge

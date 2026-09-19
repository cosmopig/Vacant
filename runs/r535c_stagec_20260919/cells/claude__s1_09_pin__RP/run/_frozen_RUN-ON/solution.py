def solution(value, lower, upper):
    if lower <= value <= upper:
        return value
    elif value < lower:
        return lower
    else:
        return upper

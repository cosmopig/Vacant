def flat(nested):
    result = []
    for sublist in nested:
        for item in sublist:
            result.append(item)
    return result

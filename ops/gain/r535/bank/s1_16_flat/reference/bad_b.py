def flat(nested):
    return tuple(x for inner in nested for x in inner)

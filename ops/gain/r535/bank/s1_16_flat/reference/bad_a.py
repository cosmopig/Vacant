def flat(nested):
    return sorted(x for inner in nested for x in inner)

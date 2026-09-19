def solve(lookup):
    new_lookup = {}
    for key, value in lookup.items():
        new_lookup[value] = key
    return new_lookup

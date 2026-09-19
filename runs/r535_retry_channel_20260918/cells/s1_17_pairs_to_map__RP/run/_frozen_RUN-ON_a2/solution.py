def pairs_to_map(keys, values):
    lookup = {}
    for i in range(len(keys)):
        lookup[keys[i]] = values[i]
    return lookup

if __name__ == "__main__":
    keys = ["a", "b", "c", "a"]
    values = [1, 2, 3, 4]
    print(pairs_to_map(keys, values))  # Expected output: {'a': 4, 'b': 2, 'c': 3}

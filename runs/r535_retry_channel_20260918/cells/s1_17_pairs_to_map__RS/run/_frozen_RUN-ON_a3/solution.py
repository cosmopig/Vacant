def build_lookup(keys, values):
    lookup = {}
    for key, value in zip(keys, values):
        lookup[key] = value
    return lookup

# Example usage:
if __name__ == "__main__":
    keys = ["a", "b", "c", "a"]
    values = [1, 2, 3, 4]
    print(build_lookup(keys, values))  # Expected output: {'a': 4, 'b': 2, 'c': 3}

def pairs_to_map(keys, values):
    """
    Builds a lookup mapping each key to the value at the same position.
    If a key appears multiple times, the last occurrence's value is kept.
    """
    mapping = {}
    for i in range(len(keys)):
        mapping[keys[i]] = values[i]
    return mapping

# Example usage:
if __name__ == "__main__":
    keys = ["a", "b", "c", "a"]
    values = [1, 2, 3, 4]
    print(pairs_to_map(keys, values))  # Expected output: {'a': 4, 'b': 2, 'c': 3}

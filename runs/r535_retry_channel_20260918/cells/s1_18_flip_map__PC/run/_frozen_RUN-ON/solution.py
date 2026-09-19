def flip_map(d):
    flipped = {}
    for k, v in d.items():
        flipped[v] = k
    return flipped

if __name__ == "__main__":
    # Test cases
    print(flip_map({'a': 1, 'b': 2}))  # Expected: {1: 'a', 2: 'b'}
    print(flip_map({'a': 1, 'b': 1}))  # Expected: {1: 'b'} (later one wins)
    print(flip_map({'x': 'y', 'z': 'x'})) # Expected: {'y': 'x', 'x': 'z'}

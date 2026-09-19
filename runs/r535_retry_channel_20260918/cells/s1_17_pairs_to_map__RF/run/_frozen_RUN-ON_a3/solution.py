def solution(keys, values):
    lookup = {}
    for i in range(len(keys)):
        lookup[keys[i]] = values[i]
    return lookup

if __name__ == "__main__":
    # Example usage:
    keys = ["a", "b", "c", "a"]
    values = [1, 2, 3, 4]
    print(solution(keys, values))  # Expected output: {'a': 4, 'b': 2, 'c': 3}

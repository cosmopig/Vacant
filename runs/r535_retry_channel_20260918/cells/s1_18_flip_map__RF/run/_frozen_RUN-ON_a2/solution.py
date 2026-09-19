def solve(lookup):
    new_lookup = {}
    for key, value in lookup.items():
        new_lookup[value] = key
    return new_lookup

# Example usage (not required by task but for testing)
if __name__ == "__main__":
    test_input = {"a": 1, "b": 2, "c": 1}
    # Expected: {1: "c", 2: "b"} because "c" comes later than "a"
    print(solve(test_input))

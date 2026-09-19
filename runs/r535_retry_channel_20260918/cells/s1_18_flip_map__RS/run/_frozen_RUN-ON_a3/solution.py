def invert_lookup(data):
    inverted = {}
    for key, value in data.items():
        # If the value already exists as a key in our new dict, 
        # it will be overwritten by the current key because we are 
        # iterating in order and the task says "the one that comes later 
        # in the original is the one that wins".
        # Wait, if two keys share a value, e.g., {"a": 1, "b": 1}
        # The result should be {1: "b"}.
        # My loop:
        # key="a", value=1 -> inverted[1] = "a"
        # key="b", value=1 -> inverted[1] = "b" (overwrites)
        inverted[value] = key
    return inverted

# Example usage based on description:
# input: {"a": 1, "b": 2, "c": 1}
# output: {1: "c", 2: "b"}
if __name__ == "__main__":
    # The task doesn't specify the input format (dict, list of tuples, etc.)
    # Usually "lookup" implies a dictionary.
    example_input = {"a": 1, "b": 2, "c": 1}
    print(invert_lookup(example_input))

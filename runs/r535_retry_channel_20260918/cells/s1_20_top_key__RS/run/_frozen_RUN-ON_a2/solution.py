def solution(lookup):
    if not lookup:
        return None
    
    # Find the maximum count
    max_count = max(lookup.values())
    
    # Filter names that have the maximum count
    candidates = [name for name, count in lookup.items() if count == max_count]
    
    # Sort candidates alphabetically and return the first one
    return sorted(candidates)[0]

# Example usage:
if __name__ == "__main__":
    test_cases = [
        ({"apple": 5, "banana": 10, "cherry": 10}, "banana"),
        ({"a": 1, "b": 2, "c": 2}, "b"),
        ({"z": 100, "y": 100, "x": 100}, "x"),
        ({"hello": 1}, "hello")
    ]
    
    for lookup, expected in test_cases:
        result = solution(lookup)
        print(f"Lookup: {lookup} | Expected: {expected} | Got: {result}")

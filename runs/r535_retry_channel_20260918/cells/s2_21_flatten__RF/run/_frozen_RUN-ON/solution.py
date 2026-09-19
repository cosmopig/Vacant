from typing import List, Any

def flatten(xs: List[Any]) -> List[Any]:
    """
    Flattens a list where elements are either single items or lists of items.
    
    Args:
        xs: A list containing items and/or nested lists of items.
        
    Returns:
        A flat list containing all individual items.
    """
    result = []
    for item in xs:
        if isinstance(item, list):
            # If the worker put a list in, we extend our result with its contents
            result.extend(flatten(item))
        else:
            # If the worker put exactly one answer (not a list), we append it
            result.append(item)
    return result

if __name__ == "__main__":
    # Examples to test the solution
    test_cases = [
        ([1, 2, [3, 4], 5], [1, 2, 3, 4, 5]),
        ([[1, 2], [3]], [1, 2, 3]),
        ([1, [2, [3, 4]]], [1, 2, 3, 4]),
        ([], []),
        ([[[]], [1]], [1])
    ]

    for input_data, expected in test_cases:
        actual = flatten(input_data)
        assert actual == expected, f"Failed for {input_data}: expected {expected}, got {actual}"
    
    print("All tests passed!")

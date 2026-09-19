from typing import List, Any

def flatten(xs: List[Any]) -> List[Any]:
    """
    Flattens a nested list where elements are either single items or lists of items.
    
    Args:
        xs: A list containing items that can be either individual values 
            or lists of values.
            
    Returns:
        A flattened list containing all the individual values.
    """
    result = []
    for item in xs:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result

# Example usage:
if __name__ == "__main__":
    test_input = [1, [2, 3], [[4], 5], 6]
    expected_output = [1, 2, 3, 4, 5, 6]
    assert flatten(test_input) == expected_output
    print("Test passed!")

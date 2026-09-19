from typing import List

def flatten_list(nested_list: List[List]) -> List:
    """
    Takes a list whose entries are themselves lists and gives back one
    single list holding the inner entries in the order they appear.
    """
    result = []
    for sublist in nested_list:
        for item in sublist:
            result.append(item)
    return result

if __name__ == "__main__":
    # Example usage:
    test_input = [[1, 2], [3, 4], [5]]
    expected_output = [1, 2, 3, 4, 5]
    assert flatten_list(test_input) == expected_output
    print("Test passed!")

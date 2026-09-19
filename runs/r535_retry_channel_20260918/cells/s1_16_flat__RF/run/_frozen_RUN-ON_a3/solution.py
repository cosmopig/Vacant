from typing import List

def flatten_list(nested_list: List[List]) -> List:
    """
    Takes a list whose entries are themselves lists and gives back one
    single list holding the inner entries in the order they appear.
    """
    flat_list = []
    for sublist in nested_list:
        for item in sublist:
            flat_list.append(item)
    return flat_list

if __name__ == "__main__":
    # Example usage:
    test_input = [[1, 2], [3, 4], [5]]
    expected_output = [1, 2, 3, 4, 5]
    result = flatten_list(test_input)
    print(f"Input: {test_input}")
    print(f"Output: {result}")
    assert result == expected_output

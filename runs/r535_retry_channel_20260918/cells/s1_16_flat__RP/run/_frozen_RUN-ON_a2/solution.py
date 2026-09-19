from typing import List, Any

def flat(nested_list: List[List[Any]]) -> List[Any]:
    """
    Takes a list whose entries are themselves lists and gives back one
    single list holding the inner entries in the order they appear.
    Only one level of nesting is ever present.
    """
    flat_list = []
    for sublist in nested_list:
        for item in sublist:
            flat_list.append(item)
    return flat_list

if __name__ == "__main__":
    # Example usage:
    nested = [[1, 2], [3, 4], [5]]
    print(flat(nested))  # Expected output: [1, 2, 3, 4, 5]

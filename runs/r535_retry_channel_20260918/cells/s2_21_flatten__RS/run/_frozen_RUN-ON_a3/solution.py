from typing import List, Any

def flatten(xs: List[Any]) -> List[Any]:
    """
    Flattens a list of lists or elements into a single list.
    If an element is a list, its contents are added to the result.
    If an element is not a list (i.e., it's a single answer), it is added directly.
    """
    result = []
    for item in xs:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result

# Example usage:
# flatten([[1, 2], 3, [4, 5]]) -> [1, 2, 3, 4, 5]

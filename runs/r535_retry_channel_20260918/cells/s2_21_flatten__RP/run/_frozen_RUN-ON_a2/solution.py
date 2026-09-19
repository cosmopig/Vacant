from typing import List, Any

def flatten(xs: List[Any]) -> List[Any]:
    result = []
    for x in xs:
        if isinstance(x, list):
            result.extend(flatten(x))
        else:
            result.append(x)
    return result

# Example usage:
# print(flatten([1, [2, 3], [[4], 5]]))  # Output: [1, 2, 3, 4, 5]

from typing import List, Any

def flatten(xs: List[Any]) -> List[Any]:
    result = []
    for item in xs:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result

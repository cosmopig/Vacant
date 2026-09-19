from typing import List, Any

def flatten(xs: List[Any]) -> List[Any]:
    result = []
    for x in xs:
        if isinstance(x, list):
            result.extend(x)
        else:
            result.append(x)
    return result

from typing import List, Any

def flatten(xs: List[Any]) -> List[Any]:
    result = []
    for x in xs:
        if isinstance(x, list) and len(x) > 1:
            result.extend(flatten(x))
        else:
            # If it's a list with one element, we keep the element as is (but remove the outer list if it was meant to be just that element)
            # Wait, the requirement says "a worker that had several answers put a list in, and a worker that had exactly one put the answer itself in."
            # This means:
            # - If worker has multiple answers [A, B], they put [A, B] in. flatten should extract A and B.
            # - If worker has one answer A, they put A in. flatten should keep A.
            # BUT the input to flatten is a list of these results.
            # Example: workers produce [1, 2], 3, [[4]]
            # The input to flatten is [[1, 2], 3, [[4]]]
            # Result should be [1, 2, 3, [4]]
            if isinstance(x, list) and len(x) == 1:
                result.append(x[0])
            else:
                result.append(x)
    return result

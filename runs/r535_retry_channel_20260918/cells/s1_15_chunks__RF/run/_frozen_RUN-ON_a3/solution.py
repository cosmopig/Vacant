from typing import List, TypeVar

T = TypeVar('T')

def chunk_list(data: List[T], size: int) -> List[List[T]]:
    """
    Cut a list into consecutive pieces of a given maximum size, in order.
    The last piece is whatever is left over and may be shorter than the others.
    All the pieces come back gathered in one list, and each piece is itself a list.
    """
    if size <= 0:
        raise ValueError("Size must be greater than 0")
    
    return [data[i : i + size] for i in range(0, len(data), size)]

if __name__ == "__main__":
    # Examples
    print(chunk_list([1, 2, 3, 4, 5], 2))  # Expected: [[1, 2], [3, 4], [5]]
    print(chunk_list([1, 2, 3, 4], 2))     # Expected: [[1, 2], [3, 4]]
    print(chunk_list([1], 5))              # Expected: [[1]]
    print(chunk_list([], 3))               # Expected: []

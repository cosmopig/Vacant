from typing import List, TypeVar

T = TypeVar('T')

def chunks(items: List[T], size: int) -> List[List[T]]:
    """
    Cut a list into consecutive pieces of a given maximum size, in order.
    The last piece is whatever is left over and may be shorter than the others.
    All the pieces come back gathered in one list, and each piece is itself a list.
    """
    if size <= 0:
        raise ValueError("Size must be greater than 0")
    
    return [items[i : i + size] for i in range(0, len(items), size)]

def chunk_list(items: List[T], size: int) -> List[List[T]]:
    return chunks(items, size)


# Examples
if __name__ == "__main__":
    print(chunk_list([1, 2, 3, 4, 5], 2))  # [[1, 2], [3, 4], [5]]
    print(chunk_list([1, 2, 3, 4, 5, 6], 3))  # [[1, 2, 3], [4, 5, 6]]
    print(chunk_list([], 3))  # []

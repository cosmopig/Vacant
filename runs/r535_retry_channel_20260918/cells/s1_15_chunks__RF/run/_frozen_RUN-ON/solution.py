from typing import List, Any

def chunk_list(data: List[Any], max_size: int) -> List[List[Any]]:
    """
    Cut a list into consecutive pieces of a given maximum size, in order.
    The last piece is whatever is left over and may be shorter than the others.
    All the pieces come back gathered in one list, and each piece is itself a list.
    """
    if max_size <= 0:
        raise ValueError("max_size must be greater than 0")
    
    return [data[i : i + max_size] for i in range(0, len(data), max_size)]

# Examples
if __name__ == "__main__":
    print(chunk_list([1, 2, 3, 4, 5], 2))  # Expected: [[1, 2], [3, 4], [5]]
    print(chunk_list([1, 2, 3, 4, 5, 6], 3))  # Expected: [[1, 2, 3], [4, 5, 6]]
    print(chunk_list([], 3))  # Expected: []

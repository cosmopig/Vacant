from typing import List, Any, Optional

def column(rows: List[dict], field: str) -> List[Optional[Any]]:
    """
    Pulls one field out of every row of a list of lookups, in order, and gives back a list.
    A row that does not carry the field contributes None; it is not skipped.
    """
    return [row.get(field) for row in rows]

# Example usage:
if __name__ == "__main__":
    data = [
        {"id": 1, "name": "Alice"},
        {"id": 2},
        {"id": 3, "name": "Charlie"},
    ]
    print(column(data, "name"))  # Expected: ['Alice', None, 'Charlie']
    print(column(data, "age"))   # Expected: [None, None, None]

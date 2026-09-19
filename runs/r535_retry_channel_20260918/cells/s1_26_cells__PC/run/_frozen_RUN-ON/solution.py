def cells(line: str) -> list[str]:
    """
    Take one line of comma-separated text and give back its fields in
    order, with any spaces around each field removed.

    There are no quoted fields and no escaped commas, so every comma separates.
    A line with nothing in it has one field, and that field is text with nothing
    in it.
    """
    if not line:
        return [""]
    
    fields = line.split(',')
    return [field.strip() for field in fields]

# Example usage (optional, but good for testing):
if __name__ == "__main__":
    print(cells("  apple , banana , cherry ")) # ['apple', 'banana', 'cherry']
    print(cells(""))                           # ['']
    print(cells("one,two,three"))             # ['one', 'two', 'three']

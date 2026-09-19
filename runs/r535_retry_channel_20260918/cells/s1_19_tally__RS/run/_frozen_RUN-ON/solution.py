from typing import List, Dict

def count_entries(entries: List[str]) -> Dict[str, int]:
    counts = {}
    for entry in entries:
        counts[entry] = counts.get(entry, 0) + 1
    return counts

# Example usage:
if __name__ == "__main__":
    example_list = ["apple", "banana", "apple", "orange", "banana", "apple"]
    print(count_entries(example_list))

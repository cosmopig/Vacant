def count_entries(entries):
    counts = {}
    for entry in entries:
        counts[entry] = counts.get(entry, 0) + 1
    return counts

# Example usage:
if __name__ == "__main__":
    test_list = ["apple", "banana", "apple", "orange", "banana", "apple"]
    print(count_entries(test_list))

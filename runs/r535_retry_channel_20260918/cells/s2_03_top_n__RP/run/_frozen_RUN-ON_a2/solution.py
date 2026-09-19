def top_n(counts, n):
    # Sort items by count in descending order.
    # If counts are equal, sort alphabetically by name to ensure deterministic output.
    sorted_counts = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    # Extract the first n names from the sorted list
    return [name for name, count in sorted_counts[:n]]

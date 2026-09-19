def top_n(counts, n):
    # Sort the items by count in descending order
    sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    # Extract the first n names from the sorted list
    return [name for name, count in sorted_counts[:n]]

def top_n(counts, n):
    # Sort by count descending, then by name ascending (alphabetical)
    sorted_items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    
    # Return the first n names
    return [item[0] for item in sorted_items[:n]]

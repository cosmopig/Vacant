def top_n(counts, n):
    # Sort items by count descending, then return names
    sorted_items = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [name for name, count in sorted_items[:n]]

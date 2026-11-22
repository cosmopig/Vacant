def merge_counts(*groups):
    """Sum counts per key across all input mappings, without mutating them.

    Zero and negative totals are kept. Key order follows first appearance.
    """
    merged = {}
    for group in groups:
        for key, value in group.items():
            merged[key] = merged.get(key, 0) + value
    return merged

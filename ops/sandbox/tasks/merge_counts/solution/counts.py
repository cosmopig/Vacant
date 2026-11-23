def merge_counts(*groups):
    result = {}
    for group in groups:
        for key, count in group.items():
            result[key] = result.get(key, 0) + count
    return result

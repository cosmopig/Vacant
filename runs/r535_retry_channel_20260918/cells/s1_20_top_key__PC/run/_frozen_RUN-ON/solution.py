def top_key(d):
    if not d:
        return None
    
    # Find the maximum count
    max_count = max(d.values())
    
    # Filter names that have the maximum count
    top_names = [name for name, count in d.items() if count == max_count]
    
    # Return the one that sorts earliest alphabetically
    return min(top_names)

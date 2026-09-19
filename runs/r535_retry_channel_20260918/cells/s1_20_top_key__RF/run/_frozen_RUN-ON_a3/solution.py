def solution(counts):
    # Find the maximum count first
    max_count = max(counts.values())
    
    # Filter names that have the maximum count
    best_names = [name for name, count in counts.items() if count == max_count]
    
    # Return the alphabetically smallest name among those with the maximum count
    return min(best_names)

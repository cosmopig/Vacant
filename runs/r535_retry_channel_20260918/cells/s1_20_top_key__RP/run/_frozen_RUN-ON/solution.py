def solution(lookup):
    # The lookup is never without entries.
    best_name = None
    max_count = -1

    # Sort keys alphabetically to handle ties correctly
    for name in sorted(lookup.keys()):
        count = lookup[name]
        if count > max_count:
            max_count = count
            best_name = name
            
    return best_name

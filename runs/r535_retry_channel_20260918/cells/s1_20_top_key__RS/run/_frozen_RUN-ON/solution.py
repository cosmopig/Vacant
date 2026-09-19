def solution(lookup):
    if not lookup:
        return None
    
    # Find the maximum count
    max_count = max(lookup.values())
    
    # Filter names that have the maximum count
    candidates = [name for name, count in lookup.items() if count == max_count]
    
    # Sort candidates alphabetically and return the first one
    return sorted(candidates)[0]

# Example usage:
# print(solution({"apple": 5, "banana": 10, "cherry": 10})) # Should output "banana"
# print(solution({"zebra": 1, "alpha": 1}))                   # Should output "alpha"

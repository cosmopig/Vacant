def solution(counts):
    if not counts:
        return None
    
    max_count = -1
    best_name = ""
    
    for name, count in counts.items():
        if count > max_count:
            max_count = count
            best_name = name
        elif count == max_count:
            if name < best_name:
                best_name = name
                
    return best_name

# Example usage (optional, for testing):
# counts = {"apple": 5, "banana": 10, "cherry": 10}
# print(solution(counts)) # Should output "banana"

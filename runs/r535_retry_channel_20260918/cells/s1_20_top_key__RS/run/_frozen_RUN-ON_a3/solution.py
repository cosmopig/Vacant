def solution(lookup):
    if not lookup:
        return None
    
    max_count = -1
    best_name = ""
    
    for name, count in lookup.items():
        if count > max_count:
            max_count = count
            best_name = name
        elif count == max_count:
            if name < best_name:
                best_name = name
                
    return best_name

# Example usage (not required by the task but good for testing):
# print(solution({"apple": 5, "banana": 10, "cherry": 10})) # Should output "banana"
# print(solution({"zebra": 20, "alpha": 20}))                 # Should output "alpha"

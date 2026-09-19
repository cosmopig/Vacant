def solution(text):
    if not text:
        return None
    
    max_char = ""
    max_len = 0
    current_char = ""
    current_len = 0
    
    # To handle the "started earlier" requirement, we only update max_len
    # if current_len is strictly greater than max_len.
    
    for char in text:
        if char == current_char:
            current_len += 1
        else:
            if current_len > max_len:
                max_len = current_len
                max_char = current_char
            current_char = char
            current_len = 1
            
    # Final check for the last stretch
    if current_len > max_len:
        max_len = current_len
        max_char = current_char
        
    return {"character": max_char, "length": max_len}

# Example usage (optional, but good for testing):
# print(solution("aaabbbbbaaaa")) # Should return {'character': 'b', 'length': 5}
# print(solution("aabb"))         # Should return {'character': 'a', 'length': 2}

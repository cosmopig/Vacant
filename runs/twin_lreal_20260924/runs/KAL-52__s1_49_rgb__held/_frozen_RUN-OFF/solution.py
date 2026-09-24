def solution(color_hash):
    # Remove the hash character
    hex_str = color_hash[1:]
    
    # Convert hex to integers for each channel
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    
    return {"r": r, "g": g, "b": b}

# Example usage (optional for testing):
# print(solution("#FFFFFF"))  # {'r': 255, 'g': 255, 'b': 255}
# print(solution("#000000"))  # {'r': 0, 'g': 0, 'b': 0}
# print(solution("#ff5733"))  # {'r': 255, 'g': 87, 'b': 51}

def rgb(code):
    # Remove the hash character
    hex_str = code[1:]
    
    # Convert hex to integers for each channel
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    
    return {"r": r, "g": g, "b": b}

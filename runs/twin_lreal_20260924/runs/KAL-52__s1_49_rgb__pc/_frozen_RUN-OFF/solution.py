def rgb(code):
    # Remove the hash character
    hex_code = code[1:]
    
    # Convert hex to integers for each pair of digits
    r = int(hex_code[0:2], 16)
    g = int(hex_code[2:4], 16)
    b = int(hex_code[4:6], 16)
    
    return {"r": r, "g": g, "b": b}

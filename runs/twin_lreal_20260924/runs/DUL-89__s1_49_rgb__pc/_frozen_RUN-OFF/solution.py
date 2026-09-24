def rgb(code):
    # Remove the hash character
    hex_code = code[1:]
    
    # Convert hex to integer
    rgb_int = int(hex_code, 16)
    
    # Extract r, g, b components
    r = (rgb_int >> 16) & 0xFF
    g = (rgb_int >> 8) & 0xFF
    b = rgb_int & 0xFF
    
    return {"r": r, "g": g, "b": b}

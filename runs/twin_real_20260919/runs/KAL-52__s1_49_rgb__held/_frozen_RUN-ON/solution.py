def solution(hex_code):
    # Remove the hash character if present
    hex_code = hex_code.lstrip('#')
    
    # Convert hexadecimal to integer and then to RGB components
    r = int(hex_code[0:2], 16)
    g = int(hex_code[2:4], 16)
    b = int(hex_code[4:6], 16)
    
    return {"r": r, "g": g, "b": b}

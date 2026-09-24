def hex_to_rgb(hex_color):
    # Remove the hash character if present
    hex_code = hex_color.lstrip('#')
    
    # Convert hexadecimal to integer and then to RGB components
    r = int(hex_code[0:2], 16)
    g = int(hex_code[2:4], 16)
    b = int(hex_code[4:6], 16)
    
    return {"r": r, "g": g, "b": b}

if __name__ == "__main__":
    import sys
    # Read from stdin as it's the most common way for these tasks
    input_data = sys.stdin.read().strip()
    if input_data:
        print(hex_to_rgb(input_data))

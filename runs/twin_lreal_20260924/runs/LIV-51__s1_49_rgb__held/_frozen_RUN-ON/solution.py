def hex_to_rgb(hex_str):
    # Remove the hash character if present
    hex_val = hex_str.lstrip('#')
    
    # Convert hexadecimal to integer
    rgb_int = int(hex_val, 16)
    
    # Extract R, G, B components
    r = (rgb_int >> 16) & 0xFF
    g = (rgb_int >> 8) & 0xFF
    b = rgb_int & 0xFF
    
    return {"r": r, "g": g, "b": b}

if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        line = line.strip()
        if line:
            print(hex_to_rgb(line))

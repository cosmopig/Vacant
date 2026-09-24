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
    # Read from stdin as is common in these types of tasks
    line = sys.stdin.read().strip()
    if line:
        result = hex_to_rgb(line)
        print(result)

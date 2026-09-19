def hex_to_rgb(hex_color):
    """
    Converts a hex color string (e.g., '#FFFFFF' or 'ffffff') 
    to an RGB dictionary of integers.
    """
    # Remove the hash if it exists
    hex_color = hex_color.lstrip('#')
    
    # Convert hexadecimal to integer
    rgb_int = int(hex_color, 16)
    
    # Extract R, G, B components
    r = (rgb_int >> 16) & 0xFF
    g = (rgb_int >> 8) & 0xFF
    b = rgb_int & 0xFF
    
    return {"red": r, "green": g, "blue": b}

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(hex_to_rgb(sys.argv[1]))

import sys

def hex_to_rgb(hex_color):
    # Remove the hash if present
    hex_color = hex_color.lstrip('#')
    
    # Convert hexadecimal to integer
    rgb_int = int(hex_color, 16)
    
    # Extract R, G, B components
    r = (rgb_int >> 16) & 0xFF
    g = (rgb_int >> 8) & 0xFF
    b = rgb_int & 0xFF
    
    return {"r": r, "g": g, "b": b}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        color = sys.argv[1]
        print(hex_to_rgb(color))

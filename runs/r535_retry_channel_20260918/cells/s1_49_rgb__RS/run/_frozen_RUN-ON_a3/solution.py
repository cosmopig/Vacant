import sys

def hex_to_rgb(hex_color):
    # Remove the hash if it exists
    hex_color = hex_color.lstrip('#')
    
    # Convert hexadecimal to integer
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    return {"r": r, "g": g, "b": b}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(hex_to_rgb(sys.argv[1]))

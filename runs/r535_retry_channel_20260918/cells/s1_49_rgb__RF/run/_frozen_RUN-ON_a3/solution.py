import sys
import json

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
    # The task says: "Read a colour written the way a stylesheet writes it"
    # Usually this means from stdin or as an argument. 
    # Since no specific input method is mentioned other than "read", 
    # and standard practice for these tasks is often reading from stdin.
    # However, let's check if there are any clues in the environment.
    # I will assume it should read from stdin as a single line.
    input_data = sys.stdin.read().strip()
    if input_data:
        result = hex_to_rgb(input_data)
        print(json.dumps(result))

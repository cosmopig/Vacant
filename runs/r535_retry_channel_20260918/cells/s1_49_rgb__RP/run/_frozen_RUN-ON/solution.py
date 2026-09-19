def solve_color(hex_str):
    # Remove the hash character if present
    hex_str = hex_str.lstrip('#')
    
    # Convert each pair of hexadecimal digits to an integer
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    
    # Return the three channel values in one object (dictionary)
    return {"r": r, "g": g, "b": b}

if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        line = line.strip()
        if line:
            print(solve_color(line))

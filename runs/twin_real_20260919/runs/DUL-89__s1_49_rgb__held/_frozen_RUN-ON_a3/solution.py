def hex_to_rgb(hex_color):
    hex_str = hex_color.lstrip('#')
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    return {"r": r, "g": g, "b": b}

if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        color = line.strip()
        if color:
            print(hex_to_rgb(color))

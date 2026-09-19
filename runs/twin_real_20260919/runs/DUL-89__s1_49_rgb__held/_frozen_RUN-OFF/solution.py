def hex_to_rgb(hex_code):
    hex_code = hex_code.lstrip('#')
    r = int(hex_code[0:2], 16)
    g = int(hex_code[2:4], 16)
    b = int(hex_code[4:6], 16)
    return {"r": r, "g": g, "b": b}

if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        line = line.strip()
        if line:
            print(hex_to_rgb(line))

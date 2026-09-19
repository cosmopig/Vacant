def hex_to_rgb(code):
    t = code.lstrip("#")
    return {"r": int(t[0:2], 16), "g": int(t[2:4], 16), "b": int(t[4:6], 16)}

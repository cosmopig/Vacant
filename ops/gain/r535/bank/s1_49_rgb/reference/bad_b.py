def rgb(code):
    t = code.lstrip("#")
    return (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16))

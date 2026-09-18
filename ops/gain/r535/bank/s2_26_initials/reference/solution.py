def initials(name):
    out = []
    for part in name.split():
        for piece in part.split("-"):
            if piece:
                out.append(piece[0].upper() + ".")
    return "".join(out)

def split_path(p):
    # Find the last slash to separate the folder part
    if '/' in p:
        dir_part, rest = p.rsplit('/', 1)
    else:
        dir_part, rest = "", p

    # Find the last dot in the remaining part to separate name and extension
    if '.' in rest:
        name_part, ext_part = rest.rsplit('.', 1)
        ext = ext_part
    else:
        name_part, ext = rest, ""

    return {"dir": dir_part, "name": name_part, "ext": ext}

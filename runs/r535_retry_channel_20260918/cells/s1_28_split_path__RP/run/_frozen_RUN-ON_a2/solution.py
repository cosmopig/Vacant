def split_path(path):
    # Find the last slash to separate folder part from filename
    if '/' in path:
        folder_part, rest = path.rsplit('/', 1)
    else:
        folder_part, rest = "", path

    # Now handle the filename and extension
    if '.' in rest:
        filename_part, extension_part = rest.rsplit('.', 1)
        extension = extension_part
    else:
        filename_part = rest
        extension = ""

    return {
        "dir": folder_part,
        "name": filename_part,
        "ext": extension
    }

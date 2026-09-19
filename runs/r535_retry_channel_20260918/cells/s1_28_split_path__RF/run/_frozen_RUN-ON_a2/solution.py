def split_path(path):
    # Find the last slash to separate folder part from filename
    if '/' in path:
        folder_part, rest = path.rsplit('/', 1)
    else:
        folder_part, rest = "", path

    # Now handle the filename and extension
    if '.' in rest:
        filename_no_ext, extension = rest.rsplit('.', 1)
    else:
        filename_no_ext, extension = rest, ""

    return {
        "folder": folder_part,
        "name": filename_no_ext,
        "extension": extension
    }

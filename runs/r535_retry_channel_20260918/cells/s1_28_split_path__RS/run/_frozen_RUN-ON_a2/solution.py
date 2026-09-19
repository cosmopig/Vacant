def split_path(path):
    # Find the last slash to separate folder part from the rest
    last_slash_index = path.rfind('/')
    if last_slash_index == -1:
        folder_part = ""
        rest = path
    else:
        folder_part = path[:last_slash_index]
        rest = path[last_slash_index + 1:]

    # Find the last dot in the rest to separate name from extension
    last_dot_index = rest.rfind('.')
    if last_dot_index == -1:
        name_part = rest
        extension_part = ""
    else:
        name_part = rest[:last_dot_index]
        extension_part = rest[last_dot_index + 1:]

    return {
        "folder": folder_part,
        "name": name_part,
        "extension": extension_part
    }

if __name__ == "__main__":
    import json
    test_cases = [
        "path/to/file.txt",
        "file.txt",
        "path/to/file",
        "folder/.hidden",
        "path/to/my.file.txt"
    ]
    for tc in test_cases:
        print(json.dumps(split_path(tc)))

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
        "folder": folder_part,
        "name": filename_part,
        "extension": extension
    }

# Examples to test
if __name__ == "__main__":
    test_cases = [
        ("path/to/file.txt", {"folder": "path/to", "name": "file", "extension": "txt"}),
        ("file.txt", {"folder": "", "name": "file", "extension": "txt"}),
        ("path/to/file", {"folder": "path/to", "name": "file", "extension": ""}),
        ("path/to/file.tar.gz", {"folder": "path/to", "name": "file.tar", "extension": "gz"}),
        ("/file.txt", {"folder": "", "name": "file", "extension": "txt"}), # Wait, /file.txt -> folder is empty? 
                                                                                    # Actually rsplit('/', 1) on "/file.txt" gives ("", "file.txt")
    ]

    for path, expected in test_cases:
        result = split_path(path)
        print(f"Path: {path} -> Result: {result}, Expected: {expected}")
        assert result == expected

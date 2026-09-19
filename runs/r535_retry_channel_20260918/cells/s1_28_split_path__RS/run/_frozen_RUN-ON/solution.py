def split_path(path):
    # Find the last slash to separate folder part from filename
    if '/' in path:
        folder_part, rest = path.rsplit('/', 1)
    else:
        folder_part, rest = "", path

    # Now handle the filename and extension
    if '.' in rest:
        filename_no_ext, extension = rest.rsplit('.', 1)
        extension = extension  # Remove dot is already handled by rsplit if we want just the part after dot
    else:
        filename_no_ext, extension = rest, ""

    return {
        "folder": folder_part,
        "name": filename_no_ext,
        "extension": extension
    }

# Examples to test (optional but good for verification)
if __name__ == "__main__":
    test_cases = [
        ("folder/subfolder/file.txt", {"folder": "folder/subfolder", "name": "file", "extension": "txt"}),
        ("file.txt", {"folder": "", "name": "file", "extension": "txt"}),
        ("folder/file", {"folder": "folder", "name": "file", "extension": ""}),
        ("folder/subfolder/file.tar.gz", {"folder": "folder/subfolder", "name": "file.tar", "extension": "gz"}),
    ]

    for path, expected in test_cases:
        result = split_path(path)
        print(f"Path: {path} -> Result: {result}, Expected: {expected}")
        assert result == expected

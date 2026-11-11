import pathlib
from ops.audits.hidden_file_in_workspace_tighten import audit_workspace, get_non_trivial_lines, calculate_content_hash

def test():
    test_dir = pathlib.Path("./debug_data").resolve()
    if test_dir.exists():
        import shutil
        shutil.rmtree(test_dir)
    test_dir.mkdir()
    
    mock_ws = test_dir / "mock_ws"
    mock_ws.mkdir()
    
    hidden_lit_dir = test_dir / "mock_hidden"
    hidden_lit_dir.mkdir()
    with open(hidden_lit_dir / "test_hidden.py", "w") as f:
        f.write("solve_val = 42\n")
        
    visible_lit_dir = test_dir / "mock_visible"
    visible_lit_dir.mkdir()
    with open(visible_lit_dir / "test_visible.py", "w") as f:
        f.write("solve_val = 10\n")

    # Confirmed violation
    with open(mock_ws / "hidden_file.py", "w") as f:
        f.write("solve_val = 42\n")
    
    tar_path = mock_ws / "violation.tar.gz"
    import tarfile
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(mock_ws / "hidden_file.py", arcname="hidden_file.py")
        
    task = {
        "hidden_dir": hidden_lit_dir,
        "visible_dir": visible_lit_dir
    }
    
    print(f"Checking ws: {mock_ws}")
    results = audit_workspace(mock_ws, task)
    print(f"Results: {results}")

if __name__ == "__main__":
    test()

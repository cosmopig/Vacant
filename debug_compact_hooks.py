import pathlib
import time
from vacant_network.retention import compact_session_hooks

def test():
    tmp_path = pathlib.Path("/tmp/test_compact_hooks")
    if tmp_path.exists():
        import shutil
        shutil.rmtree(tmp_path)
    tmp_path.mkdir()
    
    hooks_dir = tmp_path / "possess" / "hooks"
    hooks_dir.mkdir(parents=True)
    
    f1 = hooks_dir / "session1.jsonl" # Oldest
    f2 = hooks_dir / "session2.jsonl" # Middle
    f3 = hooks_dir / "session3.jsonl" # Newest
    
    f1.write_text("content", encoding="utf-8")
    time.sleep(0.01)
    f2.write_text("content", encoding="utf-8")
    time.sleep(0.01)
    f3.write_text("content", encoding="utf-8")
    
    # Make f1 oversized (3MB)
    with open(f1, "wb") as f:
        f.write(b"x" * (3 * 1024 * 1024))

    print(f"Files in dir: {[f.name for f in hooks_dir.iterdir()]}")
    
    # Call compact_session_hooks
    rep = compact_session_hooks(root=tmp_path, max_file_bytes=2*1024*1024, keep_sessions=2)
    
    print(f"Rep: {rep}")

if __name__ == "__main__":
    test()

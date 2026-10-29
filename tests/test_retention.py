import pathlib
import pytest
from vacant_network.retention import gc_all, compact_session_hooks
from vacant_network.atomic import atomic_write_text

def test_gc_all_dry_run_does_not_touch_wire(tmp_path):
    # Setup: possess/proxyd/wire/
    wire_dir = tmp_path / "possess" / "proxyd" / "wire"
    wire_dir.mkdir(parents=True)
    
    req_bin = wire_dir / ".req.bin"
    resp_bin = wire_dir / ".resp.bin"
    index_jsonl = wire_dir / "index.jsonl"
    
    # Create oversized files
    req_bin.write_bytes(b"a" * 1024 * 1024) # 1MB
    resp_bin.write_bytes(b"b" * 1024 * 1024) # 1MB
    index_jsonl.write_text("dummy content", encoding="utf-8")
    
    # Call gc_all with dry_run=True
    gc_all(root=tmp_path, dry_run=True)
    
    # Assertions
    assert req_bin.exists()
    assert resp_bin.exists()
    assert index_jsonl.read_text(encoding="utf-8") == "dummy content"

def test_compact_session_hooks_no_double_count_on_oversized_old_session(tmp_path):
    # Setup: possess/hooks/
    hooks_dir = tmp_path / "possess" / "hooks"
    hooks_dir.mkdir(parents=True)
    
    # Create 3 files, oldest is oversized
    f1 = hooks_dir / "session1.jsonl" # Oldest (will be deleted)
    f2 = hooks_dir / "session2.jsonl" # Middle (kept)
    f3 = hooks_dir / "session3.jsonl" # Newest (kept)
    
    # We need to ensure f1 is the oldest in mtime sort. 
    # Since we can't easily set mtime on some filesystems, let's just rely on creation order if it works,
    # or use a small sleep. Actually, compact_session_hooks sorts by mtime.
    f1.write_text("content", encoding="utf-8")
    import time; time.sleep(0.01)
    f2.write_text("content", encoding="utf-8")
    import time; time.sleep(0.01)
    f3.write_text("content", encoding="utf-8")
    
    # Make f1 oversized (e.g., 3MB, while max_file_bytes is 2MB)
    # We need to overwrite it with large content but keep the name
    with open(f1, "wb") as f:
        f.write(b"x" * (3 * 1024 * 1024))

    # Call compact_session_hooks
    # keep_sessions=2 means f1 should be deleted, f2 and f3 kept.
    rep = compact_session_hooks(root=tmp_path, max_file_bytes=2*1024*1024, keep_sessions=2)
    
    assert rep["files_removed"] == 1
    # Since f1 was deleted and it was the only one > max_file_bytes among those kept (none),
    # files_truncated should be 0.
    assert rep["files_truncated"] == 0
    # bytes_freed should be exactly the size of f1 (3MB)
    assert rep["bytes_freed"] == 3 * 1024 * 1024

def test_compact_session_hooks_dry_run(tmp_path):
    # Setup: possess/hooks/
    hooks_dir = tmp_path / "possess" / "hooks"
    hooks_dir.mkdir(parents=True)
    
    f1 = hooks_dir / "session1.jsonl"
    f2 = hooks_dir / "session2.jsonl"
    
    f1.write_text("content", encoding="utf-8")
    import time; time.sleep(0.01)
    f2.write_text("content", encoding="utf-8")
    
    # Call compact_session_hooks with dry_run=True
    rep = compact_session_hooks(root=tmp_path, keep_sessions=1, dry_run=True)
    
    assert rep["files_removed"] == 1
    assert f1.exists()
    assert f2.exists()

def test_compact_session_hooks_truncation_accounting(tmp_path):
    # Setup: possess/hooks/
    hooks_dir = tmp_path / "possess" / "hooks"
    hooks_dir.mkdir(parents=True)
    
    f1 = hooks_dir / "session1.jsonl" # Kept, but oversized
    f2 = hooks_dir / "session2.jsonl" # Kept, small
    
    # Ensure f1 is newer than f2 so it's kept in keep_sessions=2
    f2.write_text("content", encoding="utf-8")
    import time; time.sleep(0.01)
    f1.write_text("content", encoding="utf-8")
    
    # Make f1 oversized (e.g., 3MB, while max_file_bytes is 2MB)
    with open(f1, "wb") as f:
        f.write(b"x" * (3 * 1024 * 1024))

    # Call compact_session_hooks
    # keep_sessions=2 means both are kept. f1 is > max_file_bytes so it's truncated.
    rep = compact_session_hooks(root=tmp_path, max_file_bytes=2*1024*1024, keep_sessions=2)
    
    assert rep["files_removed"] == 0
    assert rep["files_truncated"] == 1
    # bytes_freed should be exactly the amount truncated (3MB - 1MB = 2MB)
    assert rep["bytes_freed"] == 2 * 1024 * 1024

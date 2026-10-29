import os
import pathlib
import time
import shutil

from vacant_network import retention

def test_gc_all_dry_run_does_not_touch_wire():
    # 建立虛擬目錄結構，模擬 wire 通道內容
    sroot = pathlib.Path("/tmp/vacant_test_retention")
    sroot.mkdir(parents=True, exist_ok=True)
    wdir = sroot / "possess" / "proxyd" / "wire"
    wdir.mkdir(parents=True, exist_ok=True)

    # 建立兩個 body 檔案，總大小超過預設上限 (96 MiB)，但我們用小一點的測試
    # 因為 compact_wire 會讀取 _resolve_wire_body_budget()。
    # 我們手動 mock 這個行為或直接在環境變數中設定。
    os.environ["VACANT_WIRE_BODY_BYTES"] = "1024"  # 1 KB
    
    f1 = wdir / "body1"
    f2 = wdir / "body2"
    f1.write_bytes(b"a" * 600)
    f2.write_bytes(b"b" * 600)

    # 執行 dry_run gc
    rep = retention.compact_wire(root=sroot, dry_run=True)
    
    assert rep["body_bytes_freed"] == 1200
    assert f1.exists()
    assert f2.exists()
    os.environ.pop("VACANT_WIRE_BODY_BYTES", None)

def test_compact_session_hooks_no_double_count_on_oversized_old_session():
    # 建立虛擬目錄結構，模擬 hooks 目錄
    sroot = pathlib.Path("/tmp/vacant_test_retention_2")
    sroot.mkdir(parents=True, exist_ok=True)
    hdir = sroot / "possess" / "hooks"
    hdir.mkdir(parents=True, exist_ok=True)

    # 建立三個 session 檔案，其中一個是舊的且超大
    # 我們要測試：當一個檔案同時滿足「過期（被刪除）」和「單檔上限（被截斷）」時，
    # bytes_freed 只會計算一次。
    max_file_bytes = 1024 * 1024  # 1 MB
    keep_sessions = 1

    f1 = hdir / "session1.jsonl" # 最新 (mtime 會被我們手動設)
    f2 = hdir / "session2.jsonl" # 過期，且超大
    f3 = hdir / "session3.jsonl" # 過期，但小於上限

    # 內容：f1=500B, f2=2MB (超過 max_file_bytes), f3=1KB
    f1.write_bytes(b"s1" * 500)
    f2.write_bytes(b"s2" * (2 * 1024 * 1024))
    f3.write_bytes(b"s3" * 1024)

    # 手動設定 mtime：f1 最新的，f2 和 f3 是舊的
    now = time.time()
    os.utime(f1, (now, now))
    os.utime(f2, (now - 1000, now - 1000))
    os.utime(f3, (now - 2000, now - 2000))

    # 執行 compact_session_hooks
    rep = retention.compact_session_hooks(root=sroot, max_file_bytes=max_file_bytes, keep_sessions=keep_sessions)

    # 計算預期：
    # f1: 保留 (最新) -> freed=0
    # f2: 刪除 (過期) -> freed=2MB
    # f3: 刪除 (過期) -> freed=1KB
    # 如果發生 double count，f2 的 2MB 會被加兩次（一次在截斷迴圈，一次在刪除迴圈）。
    # 正確的結果應該是 2MB + 1KB = 2048 KB (或接近)。
    # 因為 f2 在 files[keep_sessions:] 中會先被處理並 unlink。
    # 然後在 files[:keep_sessions] 中，f1 會被檢查截斷（但它本身就小於上限）。
    
    assert rep["bytes_freed"] == (2 * 1024 * 1024 + 1024)
    assert f2.exists() is False
    assert f3.exists() is False
    assert f1.exists() is True

    # 清理
    shutil.rmtree(sroot)


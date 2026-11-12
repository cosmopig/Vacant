#!/usr/bin/env python3
"""Unit tests for e010 closure check audit script.

This test suite verifies the mechanical checks performed by `ops/audits/e010_closure_check.py`.
It uses a mock file system to simulate various success and failure scenarios.
"""

import argparse
import pathlib
import json
import sys
import tempfile
import subprocess
from typing import List

# Import the check function from the audit script
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from ops.audits.e010_closure_check import check, RUNS_DIR, PACKET_PATH, BACKLOG_PATH
except ImportError:
    # Fallback if the module isn't found correctly in some environments
    import importlib.util
    spec = importlib.util.spec_from_file_location("e010_closure_check", "ops/audits/e010_closure_check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ops.audits.e010_closure_check"] = module
    spec.loader.exec_module(module)
    from ops.audits.e010_closure_check import check, RUNS_DIR, PACKET_PATH, BACKLOG_PATH

def run_test(name: str, runs_dir: pathlib.Path, packet_path: pathlib.Path, backlog_path: pathlib.Path) -> bool:
    print(f"Running test: {name}")
    v = check(runs_dir, packet_path, backlog_path)
    if v:
        print(f"  FAIL: {v}")
        return False
    print("  PASS")
    return True

def test_e010_closure_check():
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        
        mock_runs = tmp / "runs"
        mock_runs.mkdir(parents=True, exist_ok=True)
        c_r1_cell = mock_runs / "bigwork-bw_repo_readme-pi-C-r1" / "cell.json"
        c_r1_cell.parent.mkdir(parents=True, exist_ok=True)
        
        mock_packet = tmp / "e010_bigwork.md"
        # Use a content that doesn't trigger the "[ ]" check in §5
        mock_packet.write_text("## 5. 實際結果\n- [x] C-r1 vacant_home_bytes <=256MiB", encoding="utf-8")
        
        # Note: The check looks for "- [x]" at the start of the line (lstrip)
        mock_backlog = tmp / "BACKLOG.md"
        mock_backlog.write_text("- [x] e010_bigwork_pi_AC (round 2026-11-12 結案 票 R20261112_0320-1)", encoding="utf-8")

        # Test Case: Correct values
        c_r1_cell.write_text(json.dumps({
            "vacant_home_bytes": 1077331,
            "vacant_objects_bytes": 1062407,
            "pass": True
        }), encoding="utf-8")
        assert run_test("Correct values", mock_runs, mock_packet, mock_backlog) is True
        
        # Test Case: Wrong vhb
        c_r1_cell.write_text(json.dumps({
            "vacant_home_bytes": 999999,
            "vacant_objects_bytes": 1062407,
            "pass": True
        }), encoding="utf-8")
        assert run_test("Wrong vhb", mock_runs, mock_packet, mock_backlog) is False

        # Test Case: Wrong pass status
        c_r1_cell.write_text(json.dumps({
            "vacant_home_bytes": 1077331,
            "vacant_objects_bytes": 1062407,
            "pass": False
        }), encoding="utf-8")
        assert run_test("Wrong pass status", mock_runs, mock_packet, mock_backlog) is False

        # Test Case: Packet with [ ] in §5
        mock_packet.write_text("## 5. 實際結果\n- [ ] C-r1 vacant_home_bytes <=256MiB", encoding="utf-8")
        assert run_test("Packet with [ ]", mock_runs, mock_packet, mock_backlog) is False

        # Test Case: Backlog not checked (missing [x])
        mock_backlog.write_text("- [ ] e010_bigwork_pi_AC (round 2026-11-12 結案 票 R20261112_0320-1)", encoding="utf-8")
        assert run_test("Backlog not checked", mock_runs, mock_packet, mock_backlog) is False

        # Test Case: Backlog missing date/ticket
        mock_backlog.write_text("- [x] e010_bigwork_pi_AC (round 2026-99-99 結案 票 R999)", encoding="utf-8")
        assert run_test("Backlog missing date/ticket", mock_runs, mock_packet, mock_backlog) is False

    print("All tests passed!")
    return 0

def test_selftest_ok():
    script = os.path.abspath("ops/audits/e010_closure_check.py")
    p = subprocess.run([sys.executable, script, "--selftest"],
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, f"Self-test failed with return code {p.returncode}\n{p.stdout + p.stderr}"
    assert "VERDICT: E010_CLOSURE_OK" in p.stdout

if __name__ == "__main__":
    # We need to make sure the module is available for pytest if it's not already
    # But since we are running this script directly, we just call the tests.
    test_e010_closure_check()

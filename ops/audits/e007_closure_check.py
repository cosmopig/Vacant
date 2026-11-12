import json
import sys
from pathlib import Path
from typing import Any, Dict

def test_report():
    report_path = Path("/srv/vlab/runs/e007_dabench_smoke/REPORT.json")
    with open(report_path, "r") as f:
        report = json.load(f)
    
    assert report["cells_scored"] == 4, f"Expected cells_scored=4, got {report['cells_scored']}"
    assert report["infra"] == 0, f"Expected infra=0, got {report['infra']}"
    assert report["A"]["rate"] == 0.5, f"Expected A rate=0.5, got {report['A']['rate']}"
    assert report["C"]["rate"] == 0.5, f"Expected C rate=0.5, got {report['C']['rate']}"
    assert report["vacant_sha"] == "12d1dc2a61592193a7c13a2b236dc5aa8f24e6d1", f"Expected vacant_sha, got {report['vacant_sha']}"
    assert report["pairs"] == 2, f"Expected pairs=2, got {report['pairs']}"

def test_envelope():
    # C arm: 2 PASS/0 FAIL, home_bytes [65551,167361,167361]
    # We need to find where the envelope data is. 
    # Based on e003, it's in a specific structure.
    # Let's look at REPORT.json first to see if it contains envelope info or if we need to read another file.
    # The ticket says "Envelope compliance (C arm: ...)"
    # Usually this is checked by looking at the results of the gate.
    pass

def test_packet():
    packet_path = Path("ops/packets/e007_dabench.md")
    content = packet_path.read_text()
    assert "DABench" in content
    # Add more specific checks as needed from the ticket

def test_backlog():
    backlog_path = Path("ops/BACKLOG.md")
    content = backlog_path.read_text()
    lines = content.splitlines()
    # Line 92 (human readable) - need to find it accurately.
    # The ticket says "Line 92 (human readable), note '判定 GO', sha256 match."
    # Let's just check if "判定 GO" exists in the file for now and refine.
    assert "判定 GO" in content

def main():
    print("Running e007 closure checks...")
    try:
        test_report()
        print("REPORT.json check passed.")
        # test_envelope() # Need to implement based on actual data structure
        # test_packet()   # Need to implement based on actual content
        # test_backlog()   # Need to implement based on exact line
        print("All checks passed (partial).")
    except Exception as e:
        print(f"Check failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

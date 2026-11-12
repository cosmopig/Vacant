import unittest
from unittest.mock import patch, mock_open
import os
import sys
from pathlib import Path

# Add current directory to path for imports if needed, 
# but we can just use the script directly or relative imports.
sys.path.append(str(Path(__file__).parent.parent))

class TestStrayLabdRootCauseAudit(unittest.TestCase):
    def test_selftest(self):
        """Verify that --selftest returns 0 and correct verdict."""
        # We can run the script as a subprocess to check exit code and stdout
        import subprocess
        result = subprocess.run(
            [sys.executable, "ops/audits/stray_labd_root_cause_audit.py", "--selftest"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: STRAY_LABD_ROOT_CAUSE_OK", result.stdout)

    def test_parse_session_evidence_valid(self):
        """Verify parsing of a valid mock session."""
        from ops.audits.stray_labd_root_cause_audit import parse_session_evidence
        mock_jsonl = [
            '{"message_id": "93a55755", "timestamp": "2026-11-03T11:15:40.431Z", "model": {"name": "lms1003qwen", "provider": "qwen/qwen3.8-27b"}, "toolCalls": [{"arguments": {"command": "kill 1638; VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &", "extra": "734502,733374"}}]}'
        ]
        with open("test_mock.jsonl", "w") as f:
            for line in mock_jsonl:
                f.write(line + "\n")
        
        events = parse_session_evidence("test_mock.jsonl")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["message_id"], "93a55755")
        os.remove("test_mock.jsonl")

    def test_audit_session_file_success(self):
        """Verify audit succeeds with correct data."""
        from ops.audits.stray_labd_root_cause_audit import audit_session_file
        mock_jsonl = [
            '{"message_id": "93a55755", "timestamp": "2026-11-03T11:15:40.431Z", "model": {"name": "lms1003qwen", "provider": "qwen/qwen3.8-27b"}, "toolCalls": [{"arguments": {"command": "kill 1638; VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &", "extra": "734502,733374"}}]}'
        ]
        with open("test_mock_success.jsonl", "w") as f:
            for line in mock_jsonl:
                f.write(line + "\n")
        
        result = audit_session_file("test_mock_success.jsonl")
        self.assertIsNotNone(result)
        self.assertEqual(result["verdict"], "STRAY_LABD_ROOT_CAUSE_OK")
        os.remove("test_mock_success.jsonl")

    def test_audit_session_file_failure_missing_command(self):
        """Verify audit fails if command is missing."""
        from ops.audits.stray_labd_root_cause_audit import audit_session_file
        mock_jsonl = [
            '{"message_id": "93a55755", "timestamp": "2026-11-03T11:15:40.431Z", "model": {"name": "lms1003qwen", "provider": "qwen/qwen3.8-27b"}, "toolCalls": [{"arguments": {"command": "wrong command"}}]}'
        ]
        with open("test_mock_fail.jsonl", "w") as f:
            for line in mock_jsonl:
                f.write(line + "\n")
        
        result = audit_session_file("test_mock_fail.jsonl")
        self.assertIsNone(result)
        os.remove("test_mock_fail.jsonl")

if __name__ == "__main__":
    unittest.main()

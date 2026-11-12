import unittest
import subprocess
import json
from pathlib import Path

class TestStrayLabdRootCauseAudit(unittest.TestCase):
    def test_selftest_success(self):
        """Verify that --selftest returns 0 and prints VERDICT: STRAY_LABD_ROOT_CAUSE_OK."""
        cmd = ["python3", "ops/audits/stray_labd_root_cause_audit.py", "--selftest"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        # The script prints the JSON result to stdout, but also prints VERDICT: STRAY_LABD_ROOT_CAUSE_OK before it?
        # Actually, looking at my audit_session_file, it prints "VERDICT: ..." then returns a dict which is dumped.
        self.assertIn("VERDICT: STRAY_LABD_ROOT_CAUSE_OK", result.stdout)

    def test_audit_missing_event(self):
        """Verify that audit fails when no labd event is found."""
        mock_content = '{"messageId": "12345", "toolCall": "ls -la"}'
        with patch("builtins.open", mock_open(read_data=mock_content)):
            cmd = ["python3", "ops/audits/stray_labd_root_cause_audit.py", "--session-file", "dummy.jsonl"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            # The script prints to stderr or stdout? Let's check both.
            self.assertTrue("ERROR: No labd launch event found" in result.stdout or "ERROR: No labd launch event found" in result.stderr)

    def test_audit_invalid_message_id(self):
        """Verify that audit fails when messageId is incorrect."""
        mock_content = json.dumps({
            "messageId": "WRONG_ID",
            "timestamp": "2026-11-03T11:15:40.431Z",
            "model": {"name": "qwen/qwen3.8-27b"},
            "toolCall": "VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &",
            "strayPid": 734502,
            "parentPid": 733374
        })
        with patch("builtins.open", mock_open(read_data=mock_content)):
            cmd = ["python3", "ops/audits/stray_labd_root_cause_audit.py", "--session-file", "dummy.jsonl"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            # The script prints to stderr or stdout? Let's check both.
            self.assertTrue("messageId WRONG_ID != 93a55755" in result.stdout or "messageId WRONG_ID != 93a55755" in result.stderr)

from unittest.mock import patch, mock_open

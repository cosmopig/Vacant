import unittest
from unittest.mock import patch, mock_open
import os
from ops.audits.stray_labd_root_cause_audit import audit_session_file

class TestStrayLabdRootCauseAudit(unittest.TestCase):
    def test_selftest_success(self):
        # The script handles --selftest by creating a mock file and running it.
        # We can just call the main logic or check if the output is correct.
        # Since we want to verify the command returns 0, let's run it via subprocess-like logic
        # but here we just test the audit_session_file function with a mock string.
        mock_data = '{"messageId": "93a55755", "timestamp": "1793704535381", "model": {"name": "qwen/qwen3.8-27b"}, "content": "kill 1638 && VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &"}'
        
        with patch("builtins.open", mock_open(read_data=mock_data)):
            result = audit_session_file("/tmp/fake_session.jsonl")
            self.assertIsNotNone(result)
            self.assertEqual(result["message_id"], "93a55755")
            self.assertEqual(result["status"], "VERIFIED")

    def test_selftest_failure_missing_command(self):
        mock_data = '{"messageId": "93a55755", "timestamp": "1793704535381", "model": {"name": "qwen/qwen3.8-27b"}, "content": "wrong command"}'
        with patch("builtins.open", mock_open(read_data=mock_data)):
            result = audit_session_file("/tmp/fake_session.jsonl")
            self.assertIsNone(result)

    def test_selftest_failure_wrong_id(self):
        mock_data = '{"messageId": "00000000", "timestamp": "1793704535381", "model": {"name": "qwen/qwen3.8-27b"}, "content": "kill 1638 && VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &"}'
        with patch("builtins.open", mock_open(read_data=mock_data)):
            result = audit_session_file("/tmp/fake_session.jsonl")
            self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()

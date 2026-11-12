import unittest
from unittest.mock import patch, mock_open
import json
import os
from ops.audits.stray_labd_root_cause_audit import audit_session_file

class TestStrayLabdRootCauseAudit(unittest.TestCase):
    def test_selftest_success(self):
        # This is tested by running the script with --selftest
        pass

    def test_parse_session_evidence_valid(self):
        mock_jsonl = json.dumps({
            "messageId": "93a55755",
            "timestamp": "2026-11-03T11:15:40.431Z",
            "model": {"name": "lms1003qwen", "provider": "qwen/qwen3.8-27b"},
            "toolCalls": [{
                "arguments": {
                    "command": "VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 & (pid=734502 parent=733374)",
                    "extra": "kill 1638"
                }
            }]
        }) + "\n"
        
        with patch("builtins.open", mock_open(read_data=mock_jsonl)):
            result = audit_session_file(
                "fake_path", 
                expected_message_id="93a55755", 
                expected_pid=734502, 
                expected_parent_pid=733374
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], "VERDICT: STRAY_LABD_ROOT_CAUSE_OK")
            self.assertEqual(result["messageId"], "93a55755")

    def test_parse_session_evidence_missing_command(self):
        mock_jsonl = json.dumps({
            "messageId": "93a55755",
            "timestamp": "2026-11-03T11:15:40.431Z",
            "toolCalls": [{
                "arguments": {
                    "command": "wrong command"
                }
            }]
        }) + "\n"
        
        with patch("builtins.open", mock_open(read_data=mock_jsonl)):
            result = audit_session_file(
                "fake_path", 
                expected_message_id="93a55755", 
                expected_pid=734502, 
                expected_parent_pid=733374
            )
            self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch, mock_open
import json
import sys
from pathlib import Path

# Add current directory to path so we can import the audit script
sys.path.append(str(Path(__file__).parent.parent.parent))
from ops.audits.stray_labd_root_cause_audit import audit_session_file

class TestStrayLabdRootCauseAudit(unittest.TestCase):
    def test_audit_success(self):
        mock_data = {
            "messageId": "93a55755",
            "timestamp": "2026-11-03T11:15:40.431Z",
            "toolCall": "kill 1638; VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &",
            "model": "lms1003qwen",
            "provider": "qwen/qwen3.8-27b",
            "stray_pid": 734502,
            "parent_pid": 733374
        }
        # Mocking the file content for parse_session_evidence
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
            result = audit_session_file("dummy_path")
            self.assertIsNotNone(result)
            self.assertEqual(result["messageId"], "93a55755")

    def test_audit_missing_command(self):
        mock_data = {
            "messageId": "93a55755",
            "timestamp": "2026-11-03T11:15:40.431Z",
            "toolCall": "echo hello",
            "model": "lms1003qwen",
            "provider": "qwen/qwen3.8-27b",
            "stray_pid": 734502,
            "parent_pid": 733374
        }
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
            result = audit_session_file("dummy_path")
            self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()

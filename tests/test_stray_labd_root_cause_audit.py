import unittest
from unittest.mock import patch, mock_open
import json
from ops.audits.stray_labd_root_cause_audit import audit_session_file

class TestStrayLabdRootCauseAudit(unittest.TestCase):
    def test_selftest_success(self):
        # This is handled by the --selftest flag in the script, 
        # but we can also test the logic directly here.
        mock_data = [
            {
                "messageId": "93a55755",
                "timestamp": "2026-11-03T11:15:40.431Z",
                "model": {"name": "lms1003qwen", "provider": "qwen/qwen3.8-27b"},
                "toolCalls": [{
                    "arguments": {
                        "command": "kill 1638; VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &"
                    }
                }]
            }
        ]
        # The issue was that mock_open(read_data=...) doesn't behave like a real file when passed to open()
        # in some contexts, or the way it's being used here.
        # Let's use a temporary file instead of mock_open for this specific test to be safe.
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            for entry in mock_data:
                tmp.write(json.dumps(entry) + "\n")
            tmp_path = tmp.name
        
        try:
            result = audit_session_file(tmp_path)
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], "STRAY_LABD_ROOT_CAUSE_OK")
            self.assertEqual(result["message_id"], "93a55755")
        finally:
            import os
            os.remove(tmp_path)

    def test_missing_command_fails(self):
        mock_data = [
            {
                "messageId": "123",
                "timestamp": "2026-11-03T11:15:40.431Z",
                "model": {"name": "lms1003qwen", "provider": "qwen/qwen3.8-27b"},
                "toolCalls": [{
                    "arguments": {
                        "command": "ls -la"
                    }
                }]
            }
        ]
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            for entry in mock_data:
                tmp.write(json.dumps(entry) + "\n")
            tmp_path = tmp.name
        
        try:
            result = audit_session_file(tmp_path)
            self.assertIsNone(result)
        finally:
            import os
            os.remove(tmp_path)

if __name__ == "__main__":
    unittest.main()

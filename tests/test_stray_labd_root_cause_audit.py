import unittest
from unittest.mock import patch, mock_open
import os
import sys
import json

# Add current directory to path for imports if needed
sys.path.append(os.getcwd())

from ops.audits.stray_labd_root_cause_audit import audit_session_file

class TestStrayLabdRootCauseAudit(unittest.TestCase):
    def test_audit_session_file_success(self):
        mock_json = json.dumps({
            "messageId": "93a55755",
            "timestamp": "2026-11-03T11:15:40.431Z",
            "model": {"name": "lms1003qwen"},
            "toolCall": "kill 1638; VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &",
            "strayPid": "734502",
            "parentPid": "733374"
        })
        with patch("builtins.open", mock_open(read_data=mock_json)):
            result = audit_session_file("fake_path")
            self.assertIsNotNone(result)
            self.assertEqual(result["verdict"], "STRAY_LABD_ROOT_CAUSE_OK")

    def test_audit_session_file_wrong_message_id(self):
        mock_json = json.dumps({
            "messageId": "WRONG",
            "timestamp": "2026-11-03T11:15:40.431Z",
            "model": {"name": "lms1003qwen"},
            "toolCall": "kill 1638; VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &",
            "strayPid": "734502",
            "parentPid": "733374"
        })
        with patch("builtins.open", mock_open(read_data=mock_json)):
            result = audit_session_file("fake_path")
            self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch, mock_open
import os
import sys
import json

# Import the functions from the audit script
# Since we are in a test file and might not have ops/audits in path, 
# we can just import it if possible or use relative imports.
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/../"))
from ops.audits.labd_instance_and_env_audit import check_labd_instances, audit_cell_env

class TestLabdAudit(unittest.TestCase):
    def test_check_labd_instances_success_zero(self):
        # Mock pgrep to return nothing (no instances)
        with patch("subprocess.check_output") as mock_pgrep:
            mock_pgrep.return_value = ""
            result = check_labd_instances()
            self.assertEqual(result, 0)

    def test_check_labd_instances_success_one(self):
        # Mock pgrep to return one instance
        with patch("subprocess.check_output") as mock_pgrep:
            mock_pgrep.return_value = "/usr/bin/python3 /path/to/labd.py"
            result = check_labd_instances()
            self.assertEqual(result, 0)

    def test_check_labd_instances_fail_multiple(self):
        # Mock pgrep to return two instances
        with patch("subprocess.check_output") as mock_pgrep:
            mock_pgrep.return_value = "/usr/bin/python3 /path/to/labd.py\n/usr/bin/python3 /path/to/labd.py"
            with self.assertRaises(SystemExit) as cm:
                check_labd_instances()
            self.assertEqual(cm.exception.code, 1)

    def test_audit_cell_env_success_clean(self):
        # Mock open to return a clean agent_env
        mock_data = json.dumps({
            "agent_env": {
                "SOME_VAR": "value",
                "OTHER_VAR": 123
            }
        })
        with patch("builtins.open", mock_open(read_data=mock_data)) as m:
            result = audit_cell_env("/fake/path/cell.json", arm="A")
            self.assertEqual(result, 0)

    def test_audit_cell_env_fail_leak_key(self):
        # Mock open to return a leak in the key
        mock_data = json.dumps({
            "agent_env": {
                "VACANT_PI_PARENT": "some_value"
            }
        })
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with self.assertRaises(SystemExit) as cm:
                audit_cell_env("/fake/path/cell.json", arm="A")
            self.assertEqual(cm.exception.code, 1)

    def test_audit_cell_env_fail_leak_value(self):
        # Mock open to return a leak in the value (PI_SELF)
        mock_data = json.dumps({
            "agent_env": {
                "MY_VAR": "pi_self_residual"
            }
        })
        with patch("builtins.open", mock_open(read_data=mock_data)):
            # The current implementation checks for "PI_SELF" in the value string
            with self.assertRaises(SystemExit) as cm:
                audit_cell_env("/fake/path/cell.json", arm="A")
            self.assertEqual(cm.exception.code, 1)

if __name__ == "__main__":
    unittest.main()

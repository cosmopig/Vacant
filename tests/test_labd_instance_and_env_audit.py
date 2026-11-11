import unittest
from unittest.mock import patch, MagicMock
import os
import json
import subprocess
from ops.audits.labd_instance_and_env_audit import check_labd_instances, audit_cell_env

class TestLabdAudit(unittest.TestCase):
    def test_check_labd_instances_with_args(self):
        # Test multiple instances (should exit 1)
        proc_list = [["python3", "/srv/vlab/bin/labd.py"], ["python3", "/srv/vlab/bin/labd.py"]]
        with self.assertRaises(SystemExit) as cm:
            check_labd_instances(proc_list=proc_list)
        self.assertEqual(cm.exception.code, 1)

    def test_check_labd_instances_with_args_single(self):
        # Test single instance (should return 1)
        proc_list = [["python3", "/srv/vlab/bin/labd.py"]]
        count = check_labd_instances(proc_list=proc_list)
        self.assertEqual(count, 1)

    def test_check_labd_instances_with_args_false_positive(self):
        # Test command containing "labd.py" but not as the script argument for python (should return 0)
        proc_list = [["python3", "/srv/vlab/bin/other_script.py"]]
        count = check_labd_instances(proc_list=proc_list)
        self.assertEqual(count, 0)

    def test_check_labd_instances_with_args_substring_false_positive(self):
        # Test command where "labd.py" is just a substring in an argument (should return 0)
        proc_list = [["python3", "/srv/vlab/bin/my_pi_session_other.py"]]
        count = check_labd_instances(proc_list=proc_list)
        self.assertEqual(count, 0)

    def test_audit_cell_env_success_a_arm_empty(self):
        # Mock cell.json with empty agent_env for A arm
        mock_data = {
            "arm": "A",
            "agent_env": {}
        }
        with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(mock_data))):
            with patch("os.path.exists", return_value=True):
                result = audit_cell_env("dummy_path", arm="A")
                self.assertTrue(result)

    def test_audit_cell_env_fail_leak_vacant_key(self):
        # Mock cell.json with VACANT_ key for A arm
        mock_data = {
            "arm": "A",
            "agent_env": {"VACANT_SECRET": "some_value"}
        }
        with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(mock_data))):
            with patch("os.path.exists", return_value=True):
                with self.assertRaises(SystemExit) as cm:
                    audit_cell_env("dummy_path", arm="A")
                self.assertEqual(cm.exception.code, 1)

    def test_audit_cell_env_fail_leak_pi_parent(self):
        # Mock cell.json with PI_PARENT in value for A arm
        mock_data = {
            "arm": "A",
            "agent_env": {"SOME_VAR": "host_PI_PARENT_value"}
        }
        with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(mock_data))):
            with patch("os.path.exists", return_value=True):
                with self.assertRaises(SystemExit) as cm:
                    audit_cell_env("dummy_path", arm="A")
                self.assertEqual(cm.exception.code, 1)

if __name__ == "__main__":
    unittest.main()

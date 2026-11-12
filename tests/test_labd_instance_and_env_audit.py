import unittest
from unittest.mock import patch
import contextlib
import io
import json
from ops.audits.labd_instance_and_env_audit import (
    check_labd_instances, audit_cell_env, audit_run_dir, agent_env_leaks,
)

LABD_CMDLINE = ["/usr/bin/python3", "/srv/vlab/bin/labd.py"]

class TestLabdAudit(unittest.TestCase):
    def test_check_labd_instances_zero(self):
        # 0 instances -> 0
        self.assertEqual(check_labd_instances(proc_list=[]), 0)

    def test_check_labd_instances_one(self):
        # 1 instance (real live shape: python interpreter + labd.py) -> 1
        self.assertEqual(check_labd_instances(proc_list=[list(LABD_CMDLINE)]), 1)

    def test_check_labd_instances_one_dict_entry(self):
        # collect_processes() entry shape: dict with "cmdline"
        entry = {"pid": 1734, "ppid": 1656, "cmdline": list(LABD_CMDLINE), "env": None}
        self.assertEqual(check_labd_instances(proc_list=[entry]), 1)

    def test_check_labd_instances_substring_not_labd(self):
        # args merely mention "labd.py" (pgrep -f substring false positive) -> 0
        self.assertEqual(
            check_labd_instances(proc_list=[["pi", "-p", "工單文字提到 labd.py"]]), 0)

    def test_check_labd_instances_bare_pid_strings_not_labd(self):
        # bare pid tokens are judged by the same is_labd rule -> never a match
        self.assertEqual(check_labd_instances(proc_list=["12345", "67890"]), 0)

    def test_check_labd_instances_multiple_exits_1(self):
        # >1 instances -> SystemExit(1) with the MULTIPLE_LABD_INSTANCES message
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as cm:
                check_labd_instances(proc_list=[["python3", "/a/labd.py"],
                                                ["python3", "/b/labd.py"],
                                                ["python3", "/c/labd.py"]])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("ERROR: MULTIPLE_LABD_INSTANCES detected. Count: 3", buf.getvalue())

    def test_check_labd_instances_live_path_uses_collect_processes(self):
        # proc_list=None must go through the /proc collector (is_labd matcher), not pgrep
        with patch("ops.audits.labd_instance_and_env_audit.collect_processes",
                   return_value=[{"cmdline": list(LABD_CMDLINE)}]):
            self.assertEqual(check_labd_instances(), 1)

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

def test_audit_run_dir(tmp_path):
    # 1843-2：audit_run_dir 批量稽核——正/負控制、infra 快照目錄排除、缺 cell.json 點名
    run = tmp_path / "run"
    (run / "cell_ok").mkdir(parents=True)
    (run / "cell_ok" / "cell.json").write_text(json.dumps(
        {"agent_env": {"VACANT_FAILED_STEP_REVIEW": "true"}}))  # C-nf 臂參數、非洩漏
    (run / "cell_leak").mkdir()
    (run / "cell_leak" / "cell.json").write_text(json.dumps(
        {"agent_env": {"VACANT_PI_SELF": "5678", "OTHER": "x"}}))
    infra = run / "cell_leak.infra-20261103T180005"
    infra.mkdir()
    (infra / "cell.json").write_text(json.dumps(
        {"agent_env": {"VACANT_PI_PARENT": "9999"}}))  # 即使洩漏也須整目錄排除
    (run / "cell_missing").mkdir()  # cell 槽目錄存在但缺 cell.json

    r = audit_run_dir(run)
    assert r["total_cells"] == 2, r
    assert r["violations"] == 1, r
    assert r["violated_cells"] == [str(run / "cell_leak" / "cell.json")], r
    assert r["clean_cells"] == [str(run / "cell_ok" / "cell.json")], r
    assert r["missing_cell_json"] == [str(run / "cell_missing" / "cell.json")], r
    blob = json.dumps([r["violated_cells"], r["clean_cells"]])
    assert "infra" not in blob, "infra 快照目錄不得計入任何一列"


def test_agent_env_leaks_fsr_not_leak():
    # C-nf 臂的 VACANT_FAILED_STEP_REVIEW 是預註冊臂定義參數，不計為洩漏
    assert agent_env_leaks({"VACANT_FAILED_STEP_REVIEW": "true"}) is False
    assert agent_env_leaks({"VACANT_PI_SELF": "1"}) is True
    assert agent_env_leaks({"VACANT_PI_PARENT": "2"}) is True
    assert agent_env_leaks(None) is False
    assert agent_env_leaks({}) is False


if __name__ == "__main__":
    unittest.main()

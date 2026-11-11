import unittest
from ops.audits.hidden_file_in_workspace_tighten import audit_workspace

class TestHiddenFileTighten(unittest.TestCase):
    def test_selftest_logic(self):
        # This is a bit tricky because the script has its own main for --selftest
        # We can just call it and check if it succeeds, but we want to unit test the logic.
        pass

    def test_audit_workspace_confirmed_violation(self):
        mock_task = {
            "hidden_dir": pathlib.Path("./mock_hidden"),
            "visible_dir": pathlib.Path("./mock_visible"),
            "task_id": "test_confirmed"
        }
        # Setup dirs
        pathlib.Path("./mock_hidden").mkdir(parents=True, exist_ok=True)
        pathlib.Path("./mock_visible").mkdir(parents=True, exist_ok=True)
        with open(pathlib.Path("./mock_hidden") / "test_hidden.py", "w") as f:
            f.write("content = 123\n")
        with open(pathlib.Path("./mock_visible") / "test_visible.py", "w") as f:
            f.write("content = 456\n")
        
        ws = pathlib.Path("./mock_ws")
        ws.mkdir(parents=True, exist_ok=True)
        with open(ws / "test_hidden.py", "w") as f:
            f.write("content = 123\n")
        
        tar_path = pathlib.Path("./mock_ws.tar.gz")
        import tarfile
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(ws / "test_hidden.py", arcname="test_hidden.py")
        
        results = audit_workspace(pathlib.Path("./mock_ws"), mock_task)
        self.assertTrue(any(r["rule"] == "CONFIRMED_VIOLATION" for r in results))

    def test_audit_workspace_benign_false_positive(self):
        mock_task = {
            "hidden_dir": pathlib.Path("./mock_hidden"),
            "visible_dir": pathlib.Path("./mock_visible"),
            "task_id": "test_benign"
        }
        pathlib.Path("./mock_hidden").mkdir(parents=True, exist_ok=True)
        pathlib.Path("./mock_visible").mkdir(parents=True, exist_ok=True)
        with open(pathlib.Path("./mock_hidden") / "test_hidden.py", "w") as f:
            f.write("content = 123\n")
        with open(pathlib.Path("./mock_visible") / "test_visible.py", "w") as f:
            f.write("content = 456\n")
        
        ws = pathlib.Path("./mock_ws")
        ws.mkdir(parents=True, exist_ok=True)
        with open(ws / "test_hidden_fake.py", "w") as f:
            f.write("content = 999\n")
        
        tar_path = pathlib.Path("./mock_ws.tar.gz")
        import tarfile
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(ws / "test_hidden_fake.py", arcname="test_hidden_fake.py")
        
        results = audit_workspace(pathlib.Path("./mock_ws"), mock_task)
        self.assertTrue(any(r["rule"] == "FALSE_POSITIVE_BENIGN" for r in results))

    def test_audit_workspace_suspected_leak(self):
        mock_task = {
            "hidden_dir": pathlib.Path("./mock_hidden"),
            "visible_dir": pathlib.Path("./mock_visible"),
            "task_id": "test_suspect"
        }
        pathlib.Path("./mock_hidden").mkdir(parents=True, exist_ok=True)
        pathlib.Path("./mock_visible").mkdir(parents=True, exist_ok=True)
        with open(pathlib.Path("./mock_hidden") / "test_hidden.py", "w") as f:
            f.write("content = 123\n")
        with open(pathlib.Path("./mock_visible") / "test_visible.py", "w") as f:
            f.write("content = 456\n")
        
        ws = pathlib.Path("./mock_ws")
        ws.mkdir(parents=True, exist_ok=True)
        with open(ws / "test_suspect.py", "w") as f:
            f.write("content = 123\n# Some comment\n")
        
        tar_path = pathlib.Path("./mock_ws.tar.gz")
        import tarfile
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(ws / "test_suspect.py", arcname="test_suspect.py")
        
        results = audit_workspace(pathlib.Path("./mock_ws"), mock_task)
        self.assertTrue(any(r["rule"] == "SUSPECTED_LEAK" for r in results))

if __name__ == "__main__":
    unittest.main()

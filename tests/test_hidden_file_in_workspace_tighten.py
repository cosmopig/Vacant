import unittest
import pathlib
import tarfile
from ops.audits.hidden_file_in_workspace_tighten import audit_workspace

class TestHiddenFileTighten(unittest.TestCase):
    def test_audit_workspace_confirmed_violation(self):
        mock_task = {
            "hidden_dir": pathlib.Path("./mock_hidden").resolve(),
            "visible_dir": pathlib.Path("./mock_visible").resolve(),
            "task_id": "test_confirmed"
        }
        pathlib.Path("./mock_hidden").mkdir(parents=True, exist_ok=True)
        pathlib.Path("./mock_visible").mkdir(parents=True, exist_ok=True)
        with open(pathlib.Path("./mock_hidden") / "test_hidden.py", "w") as f:
            f.write("content = 123\n")
        with open(pathlib.Path("./mock_visible") / "test_visible.py", "w") as f:
            f.write("content = 456\n")
        
        ws = pathlib.Path("./mock_ws").resolve()
        ws.mkdir(parents=True, exist_ok=True)
        with open(ws / "test_hidden.py", "w") as f:
            f.write("content = 123\n")
        
        tar_path = ws / "mock_ws.tar.gz"
        with tarfile.open(str(tar_path), "w:gz") as tf:
            tf.add(ws / "test_hidden.py", arcname="test_hidden.py")
        
        results = audit_workspace(ws, mock_task)
        self.assertTrue(any(r["rule"] == "CONFIRMED_VIOLATION" for r in results))

    def test_audit_workspace_benign_false_positive(self):
        mock_task = {
            "hidden_dir": pathlib.Path("./mock_hidden").resolve(),
            "visible_dir": pathlib.Path("./mock_visible").resolve(),
            "task_id": "test_benign"
        }
        pathlib.Path("./mock_hidden").mkdir(parents=True, exist_ok=True)
        pathlib.Path("./mock_visible").mkdir(parents=True, exist_ok=True)
        with open(pathlib.Path("./mock_hidden") / "test_hidden.py", "w") as f:
            f.write("content = 123\n")
        with open(pathlib.Path("./mock_visible") / "test_visible.py", "w") as f:
            f.write("content = 456\n")
        
        ws = pathlib.Path("./mock_ws").resolve()
        ws.mkdir(parents=True, exist_ok=True)
        with open(ws / "test_hidden_fake.py", "w") as f:
            f.write("content = 999\n")
        
        tar_path = ws / "mock_ws.tar.gz"
        with tarfile.open(str(tar_path), "w:gz") as tf:
            tf.add(ws / "test_hidden_fake.py", arcname="test_hidden_fake.py")
        
        results = audit_workspace(ws, mock_task)
        self.assertTrue(any(r["rule"] == "FALSE_POSITIVE_BENIGN" for r in results))

    def test_audit_workspace_suspected_leak(self):
        mock_task = {
            "hidden_dir": pathlib.Path("./mock_hidden").resolve(),
            "visible_dir": pathlib.Path("./mock_visible").resolve(),
            "task_id": "test_suspect"
        }
        pathlib.Path("./mock_hidden").mkdir(parents=True, exist_ok=True)
        pathlib.Path("./mock_visible").mkdir(parents=True, exist_ok=True)
        with open(pathlib.Path("./mock_hidden") / "test_hidden.py", "w") as f:
            f.write("content = 123\n")
        with open(pathlib.Path("./mock_visible") / "test_visible.py", "w") as f:
            f.write("content = 456\n")
        
        ws = pathlib.Path("./mock_ws").resolve()
        ws.mkdir(parents=True, exist_ok=True)
        with open(ws / "test_hidden_suspect.py", "w") as f:
            f.write("content = 123\nprint('leak')\n")
        
        tar_path = ws / "mock_ws.tar.gz"
        with tarfile.open(str(tar_path), "w:gz") as tf:
            tf.add(ws / "test_hidden_suspect.py", arcname="test_hidden_suspect.py")
        
        results = audit_workspace(ws, mock_task)
        self.assertTrue(any(r["rule"] == "SUSPECTED_LEAK" for r in results))

if __name__ == "__main__":
    unittest.main()

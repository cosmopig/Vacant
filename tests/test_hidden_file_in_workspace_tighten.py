import unittest
import pathlib
import tarfile
import json
import os
from ops.audits.hidden_file_in_workspace_tighten import audit_workspace, get_non_trivial_lines, calculate_content_hash

class TestHiddenFileTighten(unittest.TestCase):
    def setUp(self):
        self.test_dir = pathlib.Path("./test_data")
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir()
        
        self.mock_ws = self.test_dir / "mock_ws"
        self.mock_ws.mkdir()
        
        self.hidden_lit_dir = self.test_dir / "hidden_lits"
        self.hidden_lit_dir.mkdir()
        with open(self.hidden_lit_dir / "test_h1.py", "w") as f:
            f.write("val = 1\n# comment\n")
            
        self.visible_lit_dir = self.test_dir / "visible_lits"
        self.visible_lit_dir.mkdir()
        with open(self.visible_lit_dir / "test_v1.py", "w") as f:
            f.write("val = 2\n")

    def tearDown(self):
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir)

    def test_confirmed_violation(self):
        # Exact match of non-trivial lines (val = 1)
        with open(self.mock_ws / "hidden_file.py", "w") as f:
            f.write("val = 1\n# comment\n")
        
        tar_path = self.test_dir / "violation.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(self.mock_ws / "hidden_file.py", arcname="hidden_file.py")
            
        task = {
            "hidden_dir": self.hidden_lit_dir,
            "visible_dir": self.visible_lit_dir
        }
        results = audit_workspace(self.mock_ws, task)
        rules = [r["rule"] for r in results]
        self.assertIn("CONFIRMED_VIOLATION", rules)

    def test_benign_false_positive(self):
        # Different content (val = 2), no overlap with hidden lit (val = 1)
        with open(self.mock_ws / "hidden_file_fake.py", "w") as f:
            f.write("val = 2\n")
        
        tar_path = self.test_dir / "benign.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(self.mock_ws / "hidden_file_fake.py", arcname="hidden_file_fake.py")
            
        task = {
            "hidden_dir": self.hidden_lit_dir,
            "visible_dir": self.visible_lit_dir
        }
        results = audit_workspace(self.mock_ws, task)
        rules = [r["rule"] for r in results]
        # It should be FALSE_POSITIVE_BENIGN because it's not a confirmed violation 
        # and has no overlap with hidden lits.
        self.assertIn("FALSE_POSITIVE_BENIGN", rules)

    def test_suspected_leak(self):
        # Partial overlap (val = 1 is in both, but there's more content)
        with open(self.mock_ws / "leaked_file.py", "w") as f:
            f.write("val = 1\nother = 2\n")
        
        tar_path = self.test_dir / "leak.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(self.mock_ws / "leaked_file.py", arcname="leaked_file.py")
            
        task = {
            "hidden_dir": self.hidden_lit_dir,
            "visible_dir": self.visible_lit_dir
        }
        results = audit_workspace(self.mock_ws, task)
        rules = [r["rule"] for r in results]
        # It should be SUSPECTED_LEAK because it has overlap but is not an exact match of non-trivial lines
        self.assertIn("SUSPECTED_LEAK", rules)

if __name__ == "__main__":
    unittest.main()

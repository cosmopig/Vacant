import unittest
from pathlib import Path
import tarfile
from ops.audits.hidden_file_in_workspace_tighten import audit_workspace, calculate_content_hash

class TestHiddenFileTighten(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("./test_audit_data")
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir()

    def tearDown(self):
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir)

    def test_content_hash_consistency(self):
        content1 = "def solve():\n    return 42\n"
        content2 = "def solve():\n    return 42\n  # comment"
        # The hash should be the same if non-trivial lines are identical
        self.assertEqual(calculate_content_hash(content1), calculate_content_hash(content2))

    def test_audit_workspace_logic(self):
        # Setup mock directories
        hid = self.test_dir / "hidden"
        vis = self.test_dir / "visible"
        hid.mkdir()
        vis.mkdir()
        
        # Hidden lit: solve returns 42
        with open(hid / "test_h1.py", "w") as f:
            f.write("def solve():\n    return 42\n")
        # Visible lit: solve returns 10
        with open(vis / "test_v1.py", "w") as f:
            f.write("def solve():\n    return 10\n")
    
        ws = self.test_dir / "workspace"
        ws.mkdir()
    
        # Case 1: Confirmed Violation (Exact match of hidden lit)
        with open(ws / "hidden_leak.py", "w") as f:
            f.write("def solve():\n    return 42\n")
    
        # Case 2: False Positive Benign (Suspicious name, different content, no overlap)
        with open(ws / "test_hidden_fake.py", "w") as f:
            f.write("def solve():\n    return 99\n")
    
        # Case 3: Suspected Leak (Suspicious name, some overlap with hidden lit)
        with open(ws / "test_hidden_partial.py", "w") as f:
            f.write("def solve():\n    return 42\n  # but also something else")
    
        # Pack into archive
        archive = self.test_dir / "workspace.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(ws / "hidden_leak.py", arcname="hidden_leak.py")
            tf.add(ws / "test_hidden_fake.py", arcname="test_hidden_fake.py")
            tf.add(ws / "test_hidden_partial.py", arcname="test_hidden_partial.py")

        task = {
            "hidden_dir": hid,
            "visible_dir": vis
        }

        results = audit_workspace(self.test_dir / "workspace", task)
        
        rules = [r["rule"] for r in results]
        self.assertIn("CONFIRMED_VIOLATION", rules)
        self.assertIn("FALSE_POSITIVE_BENIGN", rules)
        self.assertIn("SUSPECTED_LEAK", rules)

if __name__ == "__main__":
    unittest.main()

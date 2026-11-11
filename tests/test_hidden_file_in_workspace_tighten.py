import unittest
import os
import tarfile
import io
from ops.audits.hidden_file_in_workspace_tighten import analyze_archive, get_non_trivial_lines

class TestHiddenFileTighten(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_gt_dir"
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            import shutil
            shutil.rmtree(self.test_dir)
        for f in ["mock_archive.tar.gz"]:
            if os.path.exists(f):
                os.remove(f)

    def test_get_non_trivial_lines(self):
        content = """
# This is a comment
empty line

valid_line,
another;
   spaces  
"""
        # "empty line" should be ignored because it's not non-trivial? 
        # Wait, the current implementation says: if not stripped or stripped.startswith("#"): continue
        # "empty line" is NOT empty and doesn't start with #. So it SHOULD be included.
        # But my test expected ['valid_line', 'another', 'spaces'].
        # Let's see what the current implementation does:
        # 1. "This is a comment" -> stripped starts with #, continue.
        # 2. "empty line" -> stripped is "empty line", not empty, doesn't start with #. Included.
        # 3. "" -> stripped is "", continue.
        # 4. "valid_line," -> stripped is "valid_line,", becomes "valid_line". Included.
        # 5. "another;" -> stripped is "another;", becomes "another". Included.
        # 6. "   spaces  " -> stripped is "spaces", included.
        # Result: ["empty line", "valid_line", "another", "spaces"] sorted -> ["another", "empty line", "spaces", "valid_line"]
        
        expected = ['another', 'empty line', 'spaces', 'valid_line']
        self.assertEqual(get_non_trivial_lines(content), expected)

    def test_confirmed_violation(self):
        with open(os.path.join(self.test_dir, "hidden_data.py"), "w") as f:
            f.write("import solution\ndef check(): pass")
        
        content = "import solution\ndef check(): pass"
        with tarfile.open("mock_archive.tar.gz", "w:gz") as tar:
            info = tarfile.TarInfo(name="suspicious/hidden_data.py")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content.encode("utf-8")))
        
        results = analyze_archive("mock_archive.tar.gz", self.test_dir)
        self.assertIn("suspicious/hidden_data.py", results)
        self.assertEqual(results["suspicious/hidden_data.py"]["type"], "CONFIRMED_VIOLATION")

    def test_false_positive_benign(self):
        with open(os.path.join(self.test_dir, "hidden_data.py"), "w") as f:
            f.write("import solution\ndef check(): pass")
        
        content = "print('hello world')"
        with tarfile.open("mock_archive.tar.gz", "w:gz") as tar:
            info = tarfile.TarInfo(name="suspicious/test_hidden.py")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content.encode("utf-8")))
        
        results = analyze_archive("mock_archive.tar.gz", self.test_dir)
        self.assertIn("suspicious/test_hidden.py", results)
        self.assertEqual(results["suspicious/test_hidden.py"]["type"], "FALSE_POSITIVE_BENIGN")

    def test_suspected_leak(self):
        with open(os.path.join(self.test_dir, "hidden_data.py"), "w") as f:
            f.write("import solution\ndef check(): pass")
        
        content = """
import solution
def check_something_else():
    pass
"""
        with tarfile.open("mock_archive.tar.gz", "w:gz") as tar:
            info = tarfile.TarInfo(name="suspicious/test_hidden.py")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content.encode("utf-8")))
        
        results = analyze_archive("mock_archive.tar.gz", self.test_dir)
        self.assertIn("suspicious/test_hidden.py", results)
        self.assertEqual(results["suspicious/test_hidden.py"]["type"], "SUSPECTED_LEAK")

    def test_empty_archive(self):
        with tarfile.open("mock_archive.tar.gz", "w:gz") as tar:
            pass
        results = analyze_archive("mock_archive.tar.gz", self.test_dir)
        self.assertEqual(results, {})

if __name__ == "__main__":
    unittest.main()

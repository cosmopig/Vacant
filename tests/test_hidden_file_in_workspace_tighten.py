import unittest
from ops.audits.hidden_file_in_workspace_tighten import get_non_trivial_lines, get_content_hash

class TestHiddenFileTighten(unittest.TestCase):
    def test_get_non_trivial_lines(self):
        content = """
        # This is a comment
        
        import os
        
        def solve():
            pass
        
        x = 1,
        y = 2;
        """
        expected = ["import os", "def solve():", "pass", "x = 1", "y = 2"]
        # Note: The current implementation strips trailing , and ; but keeps the rest.
        # Let's see what it actually produces.
        result = get_non_trivial_lines(content)
        self.assertIn("import os", result)
        self.assertIn("def solve():", result)
        self.assertIn("pass", result)
        self.assertNotIn("# This is a comment", result)
        self.assertNotIn("", result)

    def test_get_content_hash(self):
        lines = ["line1", "line2"]
        hash1 = get_content_hash(lines)
        hash2 = get_content_hash(["line2", "line1"])
        self.assertEqual(hash1, hash2)
        self.assertIsInstance(hash1, str)

    def test_get_non_trivial_lines_stripping(self):
        content = "x = 1,\ny = 2;"
        result = get_non_trivial_lines(content)
        self.assertEqual(result, ["x = 1", "y = 2"])

if __name__ == "__main__":
    unittest.main()

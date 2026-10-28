import unittest
import shutil
import tempfile
import json
from pathlib import Path
from ops.vlab.tools.reviewer_cost import main

class TestReviewerCost(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.cells_dir = self.test_dir / "cells"
        self.archive_dir = self.test_dir / "archive"
        self.cells_dir.mkdir()
        self.archive_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_precise_sum(self):
        cell_name = "exp-suite-task-pi-M-r1-999"
        # Create archive only (simulating already archived)
        archive_path = self.archive_dir / cell_name / "sessions"
        archive_path.mkdir(parents=True)
        
        # 3 messages with known tokens
        # msg1: in=10, out=20
        # msg2: in=5, out=5 (cacheReadInputTokens=2 -> total in=7)
        # msg3: in=100, out=200
        content = [
            '{"type":"message","message":{"usage":{"input_tokens":10,"output_tokens":20}}}',
            '{"type":"message","message":{"usage":{"input_tokens":5,"output_tokens":5,"cacheReadInputTokens":2}}}',
            '{"type":"message","message":{"usage":{"input_tokens":100,"output_tokens":200}}}'
        ]
        
        sub_dir = archive_path / "x"
        sub_dir.mkdir()
        for i, line in enumerate(content):
            (sub_dir / f"y{i}.jsonl").write_text(line)

        # Total: calls=3, in=10+7+100=117, out=20+5+200=225
        # Main costs (all 0)
        import sys
        sys.argv = ["reviewer_cost.py", "--base", str(self.cells_dir), "--out", str(self.archive_dir), "--main-calls", "0", "--main-in", "0", "--main-out", "0"]
        
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            main()
        output = json.loads(f.getvalue())
        
        self.assertEqual(len(output), 1)
        res = output[0]
        self.assertEqual(res["cell"], cell_name)
        self.assertEqual(res["model_calls"], 3)
        self.assertEqual(res["input_tokens"], 117)
        self.assertEqual(res["output_tokens"], 225)

    def test_negative_diff(self):
        cell_name = "exp-suite-task-pi-M-r1-999"
        archive_path = self.archive_dir / cell_name / "sessions"
        archive_path.mkdir(parents=True)
        
        # Total: calls=3, in=10, out=20
        content = ['{"type":"message","message":{"usage":{"input_tokens":10,"output_tokens":20}}}']
        sub_dir = archive_path / "x"
        sub_dir.mkdir()
        (sub_dir / "y0.jsonl").write_text(content[0])

        # Main costs (all 50) -> diff is negative
        import sys
        sys.argv = ["reviewer_cost.py", "--base", str(self.cells_dir), "--out", str(self.archive_dir), "--main-calls", "10", "--main-in", "50", "--main-out", "50"]
        
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            main()
        output = json.loads(f.getvalue())
        
        res = output[0]
        self.assertEqual(res["model_calls"], 0) # max(0, 3-10)
        self.assertEqual(res["input_tokens"], 0) # max(0, 10-50)
        self.assertEqual(res["output_tokens"], 0) # max(0, 20-50)
        self.assertIn("差為負", res["note"])

    def test_empty_dir(self):
        cell_name = "exp-suite-task-pi-M-r1-999"
        # No archive, no source sessions
        import sys
        sys.argv = ["reviewer_cost.py", "--base", str(self.cells_dir), "--out", str(self.archive_dir)]
        
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            main()
        output = json.loads(f.getvalue())
        
        res = output[0]
        self.assertEqual(res["model_calls"], 0)
        self.assertEqual(res["input_tokens"], 0)
        self.assertEqual(res["output_tokens"], 0)
        self.assertEqual(res["files"], [])

if __name__ == "__main__":
    unittest.main()

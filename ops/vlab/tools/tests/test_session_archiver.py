import unittest
import shutil
import tempfile
from pathlib import Path
from ops.vlab.tools.session_archiver import archive_sessions

class TestSessionArchiver(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.cells_dir = self.test_dir / "cells"
        self.archive_dir = self.test_dir / "archive"
        self.cells_dir.mkdir()
        self.archive_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_once_copy(self):
        # Create fake cell
        cell_name = "exp-suite-task-pi-M-r1-999"
        cell_path = self.cells_dir / cell_name
        cell_path.mkdir()
        
        sessions_path = cell_path / "home" / ".pi" / "agent" / "sessions"
        sessions_path.mkdir(parents=True)
        sub_dir = sessions_path / "x"
        sub_dir.mkdir()
        
        jsonl_file = sub_dir / "y.jsonl"
        jsonl_file.write_text('{"type":"message","message":{"usage":{}}}')

        archive_sessions(str(self.cells_dir), str(self.archive_dir), once=True)

        expected_path = self.archive_dir / cell_name / "sessions" / "x" / "y.jsonl"
        self.assertTrue(expected_path.exists())
        self.assertEqual(expected_path.read_text(), jsonl_file.read_text())

    def test_idempotency(self):
        cell_name = "exp-suite-task-pi-M-r1-999"
        cell_path = self.cells_dir / cell_name
        cell_path.mkdir()
        
        sessions_path = cell_path / "home" / ".pi" / "agent" / "sessions"
        sessions_path.mkdir(parents=True)
        sub_dir = sessions_path / "x"
        sub_dir.mkdir()
        
        jsonl_file = sub_dir / "y.jsonl"
        jsonl_file.write_text('{"type":"message","message":{"usage":{}}}')

        # Run once
        archive_sessions(str(self.cells_dir), str(self.archive_dir), once=True)
        expected_path = self.archive_dir / cell_name / "sessions" / "x" / "y.jsonl"
        self.assertTrue(expected_path.exists())

        # Run again - should not error or change anything significantly (shutil.copy2 overwrites)
        archive_sessions(str(self.cells_dir), str(self.archive_dir), once=True)
        self.assertTrue(expected_path.exists())

if __name__ == "__main__":
    unittest.main()

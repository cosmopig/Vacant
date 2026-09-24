"""Scoring checks for bcb_971 -- NOT part of any workspace.

This file lives in a separate tree and is never copied into an agent's
workspace. It runs every test method of the dataset's TestCases
(bigcode/bigcodebench-hard v0.1.4, BigCodeBench/971): the visible ones plus the rest.
"""

from solution import *
import sys as _vacant_sys
import solution as _vacant_solution
_vacant_sys.modules.setdefault(__name__, _vacant_solution)

import unittest
import tempfile
import os
from datetime import datetime, timezone, timedelta
class TestCases(unittest.TestCase):
    def setUp(self):
        # Set up a 'before' time with leeway for testing file modification times
        self.before_creation = datetime.now(timezone.utc) - timedelta(seconds=1)
        # Setup a temporary directory
        self.test_dir = tempfile.TemporaryDirectory()
        # Create test files
        self.files = {
            "empty.txt": 0,
            "small.txt": 5,
            "medium.txt": 50,
            "large.txt": 500,
            "utc_test.txt": 10,
        }
        for file_name, size in self.files.items():
            path = os.path.join(self.test_dir.name, file_name)
            with open(path, "wb") as f:
                f.write(os.urandom(size))
    def tearDown(self):
        # Cleanup the directory after tests
        self.test_dir.cleanup()
    def test_case_1(self):
        # Test the function on an existing directory.
        result = task_func(self.test_dir.name)
        self.assertEqual(len(result), len(self.files))
    def test_case_2(self):
        # Test the function with a non-existing directory.
        with self.assertRaises(ValueError):
            task_func("/path/to/non/existing/directory")
    def test_case_3(self):
        # Test the function with an empty directory.
        with tempfile.TemporaryDirectory() as empty_dir:
            result = task_func(empty_dir)
            self.assertEqual(len(result), 0)
    def test_case_4(self):
        # Test if the function correctly identifies file sizes.
        result = task_func(self.test_dir.name)
        sizes = {file[0]: file[1] for file in result}
        for file_name, size in self.files.items():
            self.assertEqual(sizes[file_name], size)
    def test_case_5(self):
        # Test if the function lists all expected files, regardless of order.
        result = task_func(self.test_dir.name)
        file_names = sorted([file[0] for file in result])
        expected_file_names = sorted(
            list(self.files.keys())
        )  # Assuming 'utc_test.txt' is expected.
        self.assertListEqual(file_names, expected_file_names)
    def test_case_6(self):
        # Test if modification times are correctly identified.
        result = task_func(self.test_dir.name)
        # Check if modification times are reasonable (not testing specific times because of system differences)
        for _, _, creation_time, modification_time in result:
            creation_datetime = datetime.fromisoformat(creation_time)
            modification_datetime = datetime.fromisoformat(modification_time)
            self.assertTrue(creation_datetime <= modification_datetime)
    def test_case_7(self):
        # Test that the function ignores directories.
        sub_dir_path = os.path.join(self.test_dir.name, "subdir")
        os.mkdir(sub_dir_path)
        # Add a file inside the sub-directory to ensure it's not empty
        with open(os.path.join(sub_dir_path, "file.txt"), "w") as sub_file:
            sub_file.write("This is a test.")
        result = task_func(self.test_dir.name)
        self.assertEqual(
            len(result), len(self.files)
        )  # Should not count the subdir or its contents
    def test_case_8(self):
        # Test if file names are correctly identified.
        result = task_func(self.test_dir.name)
        names = [file[0] for file in result]
        for name in self.files.keys():
            self.assertIn(name, names)
    def test_case_9(self):
        # Test that a non-directory path raises a ValueError.
        with tempfile.NamedTemporaryFile() as tmpfile:
            with self.assertRaises(ValueError):
                task_func(tmpfile.name)
    def test_case_10(self):
        # Test timestamps are in UTC and within a reasonable accuracy window.
        self.after_creation = datetime.now(timezone.utc)
        result = task_func(self.test_dir.name)
        for _, _, creation_time, modification_time in result:
            creation_dt = datetime.fromisoformat(creation_time)
            modification_dt = datetime.fromisoformat(modification_time)
            # Ensure the timestamps are in UTC
            self.assertEqual(creation_dt.tzinfo, timezone.utc)
            self.assertEqual(modification_dt.tzinfo, timezone.utc)
            # Ensure timestamps are within a reasonable window
            self.assertTrue(self.before_creation <= creation_dt <= self.after_creation)
            self.assertTrue(
                self.before_creation <= modification_dt <= self.after_creation
            )


# ── Vacant wrapper (generated by build_bank.py) ──────────────────────────
# Each check_* below runs exactly one TestCases method (with its setUp /
# tearDown) and raises AssertionError with a short message if it fails.
import unittest as _vacant_unittest

for _vacant_name in [_n for _n in list(globals()) if _n.startswith("check_")]:
    del globals()[_vacant_name]


def _vacant_short(tb_text, limit=700):
    lines = (tb_text or "").rstrip().splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.startswith("  File ")]
    tail = lines[idx[-1] + 2:] if idx and idx[-1] + 2 < len(lines) else lines[-3:]
    tail = [ln for ln in tail if ln.strip() and set(ln.strip()) - set("^~")]
    msg = "\n".join(tail).strip()
    if len(msg) > limit:
        msg = msg[: limit // 2] + " ...[cut]... " + msg[-(limit // 2):]
    return msg


def _vacant_run(method_name):
    suite = _vacant_unittest.TestSuite([TestCases(method_name)])
    result = _vacant_unittest.TestResult()
    suite.run(result)
    if result.wasSuccessful() and result.testsRun == 1:
        return
    if result.failures:
        kind, tb = "FAIL", result.failures[0][1]
    elif result.errors:
        kind, tb = "ERROR", result.errors[0][1]
    elif result.unexpectedSuccesses:
        kind, tb = "UNEXPECTED SUCCESS", ""
    else:
        kind, tb = "NOT RUN", ""
    raise AssertionError("%s %s: %s" % (kind, method_name, _vacant_short(tb)))


def check_test_case_1():
    _vacant_run('test_case_1')

def check_test_case_10():
    _vacant_run('test_case_10')

def check_test_case_2():
    _vacant_run('test_case_2')

def check_test_case_3():
    _vacant_run('test_case_3')

def check_test_case_4():
    _vacant_run('test_case_4')

def check_test_case_5():
    _vacant_run('test_case_5')

def check_test_case_6():
    _vacant_run('test_case_6')

def check_test_case_7():
    _vacant_run('test_case_7')

def check_test_case_8():
    _vacant_run('test_case_8')

def check_test_case_9():
    _vacant_run('test_case_9')

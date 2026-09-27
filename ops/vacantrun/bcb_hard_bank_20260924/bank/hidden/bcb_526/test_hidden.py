"""Scoring checks for bcb_526 -- NOT part of any workspace.

This file lives in a separate tree and is never copied into an agent's
workspace. It runs every test method of the dataset's TestCases
(bigcode/bigcodebench-hard v0.1.4, BigCodeBench/526): the visible ones plus the rest.
"""

from solution import *
import sys as _vacant_sys
import solution as _vacant_solution
_vacant_sys.modules.setdefault(__name__, _vacant_solution)

import unittest
import numpy as np
import tempfile
import json
class TestCases(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_data_paths = []
        test_data = [
            [{"a": 2, "b": 3, "c": 4}],  # Test data for test_case_1
            [{"a": 1}],  # Test data for test_case_2
            [{"a": 1.5}, {"b": None}],  # Test data for test_case_3
            [],  # Test data for test_case_4
            [{"a": 1.5, "c": 4}, {"b": None}],  # Test data for test_case_5
        ]
        for idx, data in enumerate(test_data, start=1):
            path = self.temp_dir.name + f"/test_data_{idx}.json"
            with open(path, "w") as f:
                json.dump(data, f)
            self.test_data_paths.append(path)
    def test_case_1(self):
        # Basic test
        df = task_func(self.test_data_paths[0])
        self.assertListEqual(df.index.tolist(), ["a", "b", "c"])
        self.assertAlmostEqual(df.loc["a", "mean"], 2.0)
        self.assertAlmostEqual(df.loc["a", "median"], 2.0)
    def test_case_2(self):
        # Test with a single key
        df = task_func(self.test_data_paths[1])
        self.assertListEqual(df.index.tolist(), ["a"])
        self.assertAlmostEqual(df.loc["a", "mean"], 1.0)
        self.assertAlmostEqual(df.loc["a", "median"], 1.0)
    def test_case_3(self):
        # Test with missing values to ensure handling of NaN
        df = task_func(self.test_data_paths[2])
        self.assertListEqual(df.index.tolist(), ["a", "b"])
        self.assertAlmostEqual(df.loc["a", "mean"], 1.5)
        self.assertAlmostEqual(df.loc["a", "median"], 1.5)
        self.assertTrue(np.isnan(df.loc["b", "mean"]))
        self.assertTrue(np.isnan(df.loc["b", "median"]))
    def test_case_4(self):
        # Test empty dataframe creation from an empty input file
        df = task_func(self.test_data_paths[3])
        self.assertEqual(df.shape[0], 0)
    def test_case_5(self):
        # Test handling of mixed data, including valid values and NaN
        df = task_func(self.test_data_paths[4])
        self.assertListEqual(df.index.tolist(), ["a", "b", "c"])
        self.assertAlmostEqual(df.loc["a", "mean"], 1.5)
        self.assertAlmostEqual(df.loc["a", "median"], 1.5)
        self.assertTrue(np.isnan(df.loc["b", "mean"]))
        self.assertTrue(np.isnan(df.loc["b", "median"]))
        self.assertAlmostEqual(df.loc["c", "mean"], 4.0)
        self.assertAlmostEqual(df.loc["c", "median"], 4.0)
    def test_case_6(self):
        # Test with mixed types in values
        data = [{"a": 5, "b": "text", "c": 7}, {"a": "more text", "b": 4, "c": None}]
        path = self.temp_dir.name + "/test_data_6.json"
        with open(path, "w") as f:
            json.dump(data, f)
        df = task_func(path)
        self.assertListEqual(df.index.tolist(), ["a", "b", "c"])
        self.assertAlmostEqual(df.loc["a", "mean"], 5.0)
        self.assertAlmostEqual(df.loc["c", "mean"], 7.0)
        self.assertAlmostEqual(df.loc["b", "mean"], 4.0)
    def test_case_7(self):
        # Test a larger dataset with missing values
        data = [{"a": i, "b": i * 2 if i % 2 == 0 else None} for i in range(1, 101)]
        path = self.temp_dir.name + "/test_data_7.json"
        with open(path, "w") as f:
            json.dump(data, f)
        df = task_func(path)
        self.assertAlmostEqual(df.loc["a", "mean"], 50.5)
        self.assertAlmostEqual(
            df.loc["b", "mean"], np.mean([2 * i for i in range(2, 101, 2)])
        )
    def test_case_8(self):
        # Test with all non-numeric values for a key
        data = [
            {"a": "text", "b": "more text"},
            {"a": "even more text", "b": "still more text"},
        ]
        path = self.temp_dir.name + "/test_data_8.json"
        with open(path, "w") as f:
            json.dump(data, f)
        df = task_func(path)
        self.assertTrue(np.isnan(df.loc["a", "mean"]))
        self.assertTrue(np.isnan(df.loc["b", "mean"]))
    def test_case_9(self):
        # Test varying numbers of missing and non-numeric values
        data = [
            {"a": 10, "b": 20, "c": "ignore"},
            {"a": None, "b": 25, "c": 30},
            {"a": 5, "b": "ignore", "c": "ignore"},
        ]
        path = self.temp_dir.name + "/test_data_9.json"
        with open(path, "w") as f:
            json.dump(data, f)
        df = task_func(path)
        self.assertAlmostEqual(df.loc["a", "mean"], 7.5)
        self.assertAlmostEqual(df.loc["b", "mean"], 22.5)
        self.assertAlmostEqual(df.loc["c", "mean"], 30.0)
    def tearDown(self):
        self.temp_dir.cleanup()


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

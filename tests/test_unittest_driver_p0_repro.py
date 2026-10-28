import unittest
from vacant_network.checks import run_python_check

# --- P0 Case 1: setUpClass (Expected PASS, but driver fails) ---
class TestSetUpClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = 42

    def test_value(self):
        self.assertEqual(self.value, 42)

# --- P0 Case 2: setUpModule (Expected PASS, but driver fails) ---
import sys
from types import ModuleType

mock_module = ModuleType("mock_module")
def setUpModule():
    mock_module.value = 100
setUpModule()
sys.modules["mock_module"] = mock_module

class TestSetUpModule(unittest.TestCase):
    def test_value(self):
        import mock_module
        self.assertEqual(mock_module.value, 100)

# --- P0 Case 3: expectedFailure (Expected FAIL, but driver passes) ---
class TestExpectedFailure(unittest.TestCase):
    @unittest.expectedFailure
    def test_fail(self):
        self.assertEqual(1, 2)

# --- Control Group: Normal Pass (Expected PASS, driver passes) ---
class TestNormalPass(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(1, 1)

# --- Control Group: Normal Fail (Expected FAIL, driver fails) ---
class TestNormalFail(unittest.TestCase):
    def test_fail(self):
        self.assertEqual(1, 2)

def test_p0_repro():
    candidate = "def solve(x): return x"
    
    # Case 1: setUpClass
    res1 = run_python_check(candidate, "class TestSetUpClass(unittest.TestCase):\n    @classmethod\n    def setUpClass(cls):\n        cls.value = 42\n    def test_value(self):\n        self.assertEqual(self.value, 42)", allowed_entry_points=("test_value",))
    assert res1 is False, "P0-1 (A) should be False (driver bug)"

    # Case 2: setUpModule
    res2 = run_python_check(candidate, "import sys\nfrom types import ModuleType\nmock_module = ModuleType('mock_module')\ndef setUpModule():\n    mock_module.value = 100\nsetUpModule()\nsys.modules['mock_module'] = mock_module\nclass TestSetUpModule(unittest.TestCase):\n    def test_value(self):\n        import mock_module\n        self.assertEqual(mock_module.value, 100)", allowed_entry_points=("test_value",))
    assert res2 is False, "P0-1 (B) should be False (driver bug)"

    # Case 3: expectedFailure
    res3 = run_python_check(candidate, "import unittest\nclass TestExpectedFailure(unittest.TestCase):\n    @unittest.expectedFailure\n    def test_fail(self):\n        self.assertEqual(1, 2)", allowed_entry_points=("test_fail",))
    assert res3 is True, "P0-1 (C) should be True (driver bug)"

    # Control: Normal Pass
    res4 = run_python_check(candidate, "class TestNormalPass(unittest.TestCase):\n    def test_pass(self):\n        self.assertEqual(1, 1)", allowed_entry_points=("test_pass",))
    assert res4 is True, "Control Pass should be True"

    # Control: Normal Fail
    res5 = run_python_check(candidate, "class TestNormalFail(unittest.TestCase):\n    def test_fail(self):\n        self.assertEqual(1, 2)", allowed_entry_points=("test_fail",))
    assert res5 is False, "Control Fail should be False"

if __name__ == "__main__":
    unittest.main()

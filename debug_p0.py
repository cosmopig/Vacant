from vacant_network.checks import run_python_check

def test_case1():
    candidate = "class TestCaseSetupClass(unittest.TestCase): @classmethod def setUpClass(cls): cls.shared_attr = 'initialized'; def test_method(self): self.assertEqual(self.shared_attr, 'initialized')"
    res = run_python_check(candidate, "", allowed_entry_points=("test_method",))
    print(f"P0 Case 1 (setUpClass): {res}")

def test_case2():
    # Note: setUpModule is not standard unittest. Let's see if it works as a mock-like structure.
    candidate = "class TestCaseSetupModule(unittest.TestCase): @classmethod def setUpModule(cls): cls.mod_attr = 'init'; def test_method(self): self.assertEqual(self.mod_attr, 'init')"
    res = run_python_check(candidate, "", allowed_entry_points=("test_method",))
    print(f"P0 Case 2 (setUpModule): {res}")

def test_case3():
    candidate = "import unittest; class TestCaseExpectedFailure(unittest.TestCase): @unittest.expectedFailure def test_should_fail(self): assert False"
    res = run_python_check(candidate, "", allowed_entry_points=("test_should_fail",))
    print(f"P0 Case 3 (expectedFailure): {res}")

def test_control1():
    candidate = "def test_simple_pass(): assert 1 + 1 == 2"
    res = run_python_check(candidate, "", allowed_entry_points=("test_simple_pass",))
    print(f"Control Pass: {res}")

def test_control2():
    candidate = "def test_simple_fail(): assert 1 + 1 == 3"
    res = run_python_check(candidate, "", allowed_entry_points=("test_simple_fail",))
    print(f"Control Fail: {res}")

if __name__ == "__main__":
    test_case1()
    test_case2()
    test_case3()
    test_control1()
    test_control2()

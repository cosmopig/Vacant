import unittest
from solution import hms

class TestHMS(unittest.TestCase):
    def test_check_01_hms(self):
        args = (59,)
        got = hms(*args)
        want = '00:59'
        self.assertEqual(got, want, "hms args=%r got=%r want=%r" % (args, got, want))

    def test_check_02_hms(self):
        args = (3723,)
        got = hms(*args)
        want = '1:02:03'
        self.assertEqual(got, want, "hms args=%r got=%r want=%r" % (args, got, want))

    def test_check_03_hms(self):
        args = (-1,)
        with self.assertRaises(ValueError):
            hms(*args)

if __name__ == "__main__":
    unittest.main()

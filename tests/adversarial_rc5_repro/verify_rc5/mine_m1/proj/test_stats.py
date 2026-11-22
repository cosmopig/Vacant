import unittest
from statistics import median
class T(unittest.TestCase):
    def test_median(self):
        self.assertEqual(median([3, 1, 2]), 2)
        self.assertEqual(median([5, 9, 7]), 7)

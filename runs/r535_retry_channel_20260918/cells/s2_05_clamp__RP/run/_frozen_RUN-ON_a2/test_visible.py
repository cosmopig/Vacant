import unittest
from solution import clamp

class TestClamp(unittest.TestCase):
    def test_clamp(self):
        # Standard case
        self.assertEqual(clamp(5, 0, 10), 5)
        # Below low
        self.assertEqual(clamp(-1, 0, 10), 0)
        # Above high
        self.assertEqual(clamp(11, 0, 10), 10)
        # Swapped bounds
        self.assertEqual(clamp(5, 10, 0), 5)
        # Swapped bounds below low
        self.assertEqual(clamp(-1, 10, 0), 0)
        # Swapped bounds above high
        self.assertEqual(clamp(11, 10, 0), 10)

    def test_visible_clamp(self):
        with self.assertRaises(ValueError):
            clamp(1, 10, 0)

if __name__ == "__main__":
    unittest.main()

import unittest
from queue import Q
class T(unittest.TestCase):
    def test_fifo(self):
        q=Q(); q.push(1); q.push(2); self.assertEqual(q.pop(),1)

import unittest
from solution import parse_int

class TestParseInt(unittest.TestCase):
    def check_02_parse_int(self):
        try:
            parse_int(5)
        except TypeError as e:
            return True
        except Exception as e:
            raise AssertionError("parse_int args=%r got=%s(%s) want=TypeError" % (5, type(e).__name__, e))

if __name__ == "__main__":
    unittest.main()

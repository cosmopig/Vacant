import unittest
from affine_cipher import AffineCipher

class TestAffineCipher(unittest.TestCase):
    def test_encryption_decryption(self):
        # Use a simple case: a=1, b=1 (Caesar shift 1)
        # 'ABC' -> 'BCD'
        cipher = AffineCipher(a=1, b=1)
        encrypted = cipher.encrypt("ABC")
        self.assertEqual(encrypted, "BCD")
        decrypted = cipher.decrypt("BCD")
        self.assertEqual(decrypted, "ABC")

    def test_invalid_a(self):
        # a must be coprime to 26
        with self.assertRaises(ValueError):
            AffineCipher(a=13, b=8)

if __name__ == "__main__":
    unittest.main()

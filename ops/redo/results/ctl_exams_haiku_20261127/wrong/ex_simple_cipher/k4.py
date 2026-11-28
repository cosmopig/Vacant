import random
import string


class Cipher:
    def __init__(self, key=None):
        if not key:
            key = self._generate_key()
        self.key = key

    @staticmethod
    def _generate_key(length=100):
        return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))

    def _shift(self, text, direction):
        key = self.key
        out = []
        for i, ch in enumerate(text):
            shift = ord(key[i % len(key)]) - ord('a')
            base = ord(ch) - ord('a')
            out.append(chr((base + direction * shift) % 26 + ord('a')))
        return ''.join(out)

    def encode(self, text):
        return self._shift(text, 1)

    def decode(self, text):
        return self._shift(text, -1)

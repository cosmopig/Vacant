import random
import string


class Cipher:
    def __init__(self, key=None):
        if key is None:
            key = ''.join(random.choice(string.ascii_lowercase) for _ in range(99))
        if not key or not all(c in string.ascii_lowercase for c in key):
            raise ValueError("key must be a non-empty string of lowercase letters")
        self.key = key

    def _shift(self, text, sign):
        shifts = [ord(k) - ord('a') for k in self.key]
        out = []
        for i, ch in enumerate(text):
            s = shifts[i % len(shifts)] * sign
            out.append(chr((ord(ch) - ord('a') + s) % 26 + ord('a')))
        return ''.join(out)

    def encode(self, text):
        return self._shift(text, 1)

    def decode(self, text):
        return self._shift(text, -1)

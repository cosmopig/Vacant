import random
import string


class Cipher:
    def __init__(self, key=None):
        if key is None:
            key = "".join(random.choice(string.ascii_lowercase) for _ in range(99))
        self.key = key

    def _shift(self, text, sign):
        result = []
        key_len = len(self.key)
        for i, ch in enumerate(text):
            shift = ord(self.key[i % key_len]) - ord("a")
            base = ord("a")
            offset = (ord(ch) - base + sign * shift) % 26
            result.append(chr(base + offset))
        return "".join(result)

    def encode(self, text):
        return self._shift(text, 1)

    def decode(self, text):
        return self._shift(text, -1)

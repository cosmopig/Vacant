import random
import string


class Cipher:
    def __init__(self, key=None):
        if key is None:
            key = "".join(random.choice(string.ascii_lowercase) for _ in range(100))
        self.key = key

    def _shift(self, text, sign):
        shifts = [ord(k) - ord("a") for k in self.key]
        result = []
        for i, ch in enumerate(text):
            shift = shifts[i % len(shifts)] * sign
            result.append(chr((ord(ch) - ord("a") + shift) % 26 + ord("a")))
        return "".join(result)

    def encode(self, text):
        return self._shift(text, 1)

    def decode(self, text):
        return self._shift(text, -1).encode()

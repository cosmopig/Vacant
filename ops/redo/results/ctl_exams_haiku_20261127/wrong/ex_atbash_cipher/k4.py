import string

_ALPHABET = string.ascii_lowercase
_TABLE = str.maketrans(_ALPHABET, _ALPHABET[::-1])


def _transform(text):
    text = text.lower().translate(_TABLE)
    return "".join(ch for ch in text if ch.isascii() and ch.isalnum())


def _group(text, size=5):
    return " ".join(text[i:i + size] for i in range(0, len(text) + 1, size))


def encode(plain_text):
    return _group(_transform(plain_text))


def decode(ciphered_text):
    return _transform(ciphered_text)

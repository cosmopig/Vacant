import string

_ALPHABET = string.ascii_lowercase
_TABLE = str.maketrans(_ALPHABET, _ALPHABET[::-1])
_GROUP_SIZE = 5


def _translate(text):
    cleaned = "".join(ch for ch in text.lower() if ch.isascii() and ch.isalnum())
    return cleaned.translate(_TABLE)


def _group(text):
    return " ".join(text[i:i + _GROUP_SIZE] for i in range(0, len(text), _GROUP_SIZE))


def encode(plain_text):
    return _group(_translate(plain_text))


def decode(ciphered_text):
    return _group(_translate(ciphered_text))

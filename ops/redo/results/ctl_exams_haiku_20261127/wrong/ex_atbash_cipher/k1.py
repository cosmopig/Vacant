import string

_ALPHABET = string.ascii_lowercase
_TABLE = str.maketrans(_ALPHABET, _ALPHABET[::-1])
_KEEP = set(string.ascii_lowercase + string.digits)


def _transform(text):
    cleaned = "".join(ch for ch in text.lower() if ch in _KEEP)
    return cleaned.translate(_TABLE)


def encode(plain_text):
    converted = _transform(plain_text)
    out = ""
    for index, ch in enumerate(converted, start=1):
        out += ch
        if index % 5 == 0:
            out += " "
    return out


def decode(ciphered_text):
    return _transform(ciphered_text)

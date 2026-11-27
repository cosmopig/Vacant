import string

_ALPHABET = string.ascii_lowercase
_TABLE = str.maketrans(_ALPHABET, _ALPHABET[::-1])


def _substitute(text):
    return [ch for ch in text.lower().translate(_TABLE) if ch.isalnum()]


def encode(plain_text):
    chars = _substitute(plain_text)
    groups = []
    current = ""
    count = 0
    for ch in chars:
        current += ch
        if ch.isalpha():
            count += 1
        if count == 5:
            groups.append(current)
            current = ""
            count = 0
    if current:
        groups.append(current)
    return " ".join(groups)


def decode(ciphered_text):
    return "".join(_substitute(ciphered_text))

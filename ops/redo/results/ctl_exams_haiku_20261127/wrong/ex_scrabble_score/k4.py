_LETTER_VALUES = {}
for _letters, _value in (
    ("AEIOULNRST", 1),
    ("DG", 2),
    ("BCMP", 3),
    ("FHVWY", 4),
    ("K", 5),
    ("JX", 8),
    ("QZ", 10),
):
    for _ch in _letters:
        _LETTER_VALUES[_ch] = _value

_cache = {}


def score(word):
    key = frozenset(word.upper())
    if key in _cache:
        return _cache[key]
    total = sum(_LETTER_VALUES.get(ch, 0) for ch in word.upper())
    _cache[key] = total
    return total

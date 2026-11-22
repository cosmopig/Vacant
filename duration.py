import re

_UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}
_TOKEN = re.compile(r"([0-9]+)([hms])")
_FULL = re.compile(r"\s*(?:[0-9]+[hms]\s*)+")


def parse_duration(text):
    """Parse a duration like '1h 30m' or '2m5s' into total seconds.

    The text is a sequence of tokens, each a nonnegative integer amount
    immediately followed by a unit (h, m or s). Whitespace may surround
    tokens. Empty or malformed text raises ValueError.
    """
    if not isinstance(text, str):
        raise ValueError(f"duration must be a string, got {type(text).__name__}")
    if not _FULL.fullmatch(text):
        raise ValueError(f"malformed duration: {text!r}")
    return sum(int(amount) * _UNIT_SECONDS[unit] for amount, unit in _TOKEN.findall(text))

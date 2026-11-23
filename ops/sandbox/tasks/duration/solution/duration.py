import re


def parse_duration(text):
    remaining = text.strip()
    total = 0
    if not remaining:
        raise ValueError('empty duration')
    while remaining:
        match = re.match(r'(\d+)([hms])', remaining)
        if not match:
            raise ValueError('invalid duration')
        total += int(match[1]) * {'h': 3600, 'm': 60, 's': 1}[match[2]]
        remaining = remaining[match.end():].lstrip()
    return total
